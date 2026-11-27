"""How theme tokens and the device shape the chrome: motion inputs and preference, panel
default width, elevation, coarse-pointer aims, safe areas, and phone-width wrapping."""

import pytest
from playwright.sync_api import expect
from render_cases_layout import UNBREAKABLE_PAGE
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_menu,
    panel_settled,
    resized,
    root_overflow,
    write,
)

from leaf.source.render_checks import evaluate_probe, rendered

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
                '<label><input type="checkbox">Include notes</label></section>',
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
    selection or enlarging the native mark for a finger. Their words stand on the line
    of the words beside them, whichever mark is checked, and run as one paragraph beside
    the mark, however the page marks them up."""
    source = leaf_page(
        "Preview settings",
        '<h1>Preview settings</h1><div role="group" aria-labelledby="detail">'
        '<span id="detail">Detail</span>'
        '<label><input type="radio" name="detail" value="summary" checked>'
        "<span>Summary</span></label>"
        '<label><input type="radio" name="detail" value="full">'
        "<span>Full detail</span></label></div>"
        '<label><input type="checkbox" name="notes">'
        "<span>Include notes</span></label>"
        '<div id="rich"><label><input type="checkbox" name="hq">'
        "Use <strong>high quality</strong> for every image in this report</label></div>",
        head="<style>#rich { inline-size: 12em; }</style>",
    )
    context = browser.new_context(has_touch=touch)
    page = open_page(browser, serve(source), context=context)
    full = page.get_by_role("radio", name="Full detail")
    face = page.locator("label").filter(has=full)
    before = face.bounding_box()
    words = face.get_by_text("Full detail")
    words.tap() if touch else words.click()
    expect(full).to_be_checked()
    # A mark has no words, so a choice that took its baseline from its mark would stand
    # its words above the group's label, and drop by the mark's border when checked.
    assert face.bounding_box() == before
    baselines = page.get_by_role("group", name="Detail").evaluate("""group =>
      lfUnwatched(() => [...group.querySelectorAll('span')].map(words => {
        const marker = words.appendChild(document.createElement('i'));
        marker.style.display = 'inline-block';
        const top = marker.getBoundingClientRect().top;
        marker.remove();
        return top;
      }))""")
    assert max(baselines) - min(baselines) < 0.5, baselines
    # Each line of a label holding markup starts under the first, beside the mark, as
    # a paragraph's would; laid out as a row of its parts, each part wrapped apart.
    starts = page.locator("#rich label").evaluate("""label => {
      const range = document.createRange();
      range.setStartAfter(label.querySelector('input'));
      range.setEndAfter(label.lastChild);
      const lines = new Map();
      for (const rect of range.getClientRects())
        lines.set(Math.round(rect.top), Math.min(lines.get(Math.round(rect.top)) ?? Infinity, rect.left));
      return [...lines.values()];
    }""")
    assert len(starts) > 1 and max(starts) - min(starts) < 0.5, starts
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
    readings = page.locator("main label").evaluate_all("""labels => labels.map(label => {
      const style = getComputedStyle(label), box = label.getBoundingClientRect();
      const mark = label.querySelector('input').getBoundingClientRect();
      return {height: box.height, floor: parseFloat(style.getPropertyValue('--lf-aim-floor')),
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
      const {backgroundFlash} = await window.__lfWidgetApi();
      const {motionTime} = await import('/runtime/lib/motion-timing.js');
      const chrome = document.querySelector('.lf-chrome');
      const arrival = document.createElement('button');
      arrival.className = 'lf-margin-face';
      arrival.dataset.lfAgentArrival = '1';
      chrome.append(arrival);
      const cssArrival = getComputedStyle(arrival).animationDuration;
      const cssFold = getComputedStyle(document.querySelector('lf-old')).transitionDuration;
      const animation = backgroundFlash(document.querySelector('#subject'));
      const played = animation.effect.getTiming().duration;
      animation.finish();
      arrival.remove();
      return {cssArrival, cssFold, played, fold: motionTime('--lf-motion-fold'),
        agent: motionTime('--lf-motion-agent-arrival')};
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
    assert not page.evaluate(
        "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
    ), "the page loaded under reduced motion, so the change below is none"

    page.emulate_media(reduced_motion="reduce")
    step = page.evaluate(
        "async () => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - (await window.__lfWidgetApi()).landingInsets(document.scrollingElement).bottom) * 0.6; }"
    )
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the navigation factory kept its load-time motion preference"

    page.emulate_media(reduced_motion="no-preference")

    # A glide shares a frame the page already asked for (lib/frame-pass.js), so with none
    # asked for, its frames are the ones held here.
    rendered(page)
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
    assert page.evaluate("() => document.scrollingElement.scrollTop") == 0, (
        "the step landed at once after the user asked for motion again"
    )
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
                  const range = document.createRange();
                  range.selectNodeContents(el);
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


def test_a_code_block_wraps_its_lines_whatever_holds_it(browser, serve, subtests):
    """A code block shows each line whole without scrolling sideways (reading.css,
    `pre`): a line longer than the block wraps, and its later rows hang two characters
    past its indent, so they read as the rest of the line. A box that takes its width from its
    content gives the block its line's width, so a command shows on one row in a flex
    row beside another, in an `auto` track beside an `fr` track, under a heading in a
    flex item and in a box sized to fit, and a block in a table cell keeps room for its
    words. A block whose author keeps its lines (`white-space: pre`) scrolls them
    sideways inside the column."""
    long = "const result = await fetchEverything({ retries: 3, timeout: 5000 });"
    source = leaf_page(
        "Code blocks and their holders",
        f"""<h1>Code blocks and their holders</h1>
<pre id="long"><code>{long} {long}</code></pre>
<div class="row"><pre id="start"><code>npm start</code></pre><pre id="serve"><code>uv run serve</code></pre></div>
<div class="tracks"><pre id="tracked"><code>make release</code></pre><p>From the root.</p></div>
<div class="row"><div><h2>Run</h2><pre id="labelled"><code>retry(times=5, backoff=2)</code></pre></div></div>
<div class="fitted"><h2>Run</h2><pre id="fitted"><code>uv run leaf-dev probe --state reading</code></pre></div>
<table><thead><tr><th>Run</th><th>What it does</th></tr></thead><tbody>
<tr><td><pre id="celled"><code>uv run pytest -k squeeze</code></pre></td><td>Runs the squeeze tests.</td></tr>
</tbody></table>
<pre id="kept" style="white-space: pre"><code>{long} {long}</code></pre>""",
        head="<style>.row { display: flex; gap: 16px; }"
        " .tracks { display: grid; grid-template-columns: auto 1fr; gap: 16px; }"
        " .fitted { width: fit-content; }</style>",
    )
    page = open_page(browser, serve(source))
    read = """(pre) => {
        const style = getComputedStyle(pre);
        const rows = [];
        const words = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
        for (let node; (node = words.nextNode()); ) {
          const range = document.createRange();
          range.selectNodeContents(node);
          rows.push(...[...range.getClientRects()].filter((r) => r.width > 1));
        }
        const tops = [...new Set(rows.map((r) => Math.round(r.top)))];
        const second = rows.find((r) => Math.round(r.top) === tops[1]);
        return {
          scrolls: pre.scrollWidth - pre.clientWidth,
          rows: tops.length,
          hang: second ? second.left - rows[0].left : 0,
          inside: pre.clientWidth - parseFloat(style.paddingLeft)
            - parseFloat(style.paddingRight),
          size: parseFloat(style.fontSize),
        };
    }"""
    for width in (1280, 390):
        with subtests.test(width=width):
            resized(page, width, 844)
            blocks = {
                id: page.locator(f"#{id}").evaluate(read)
                for id in ("long", "start", "serve", "tracked", "labelled", "fitted")
            }
            celled = page.locator("#celled").evaluate(read)
            kept = page.locator("#kept").evaluate(read)
            assert all(b["scrolls"] <= 1 for b in [*blocks.values(), celled]), blocks
            assert blocks["long"]["rows"] > 1, blocks["long"]
            assert blocks["long"]["hang"] > blocks["long"]["size"], blocks["long"]
            for id in ("start", "serve", "tracked", "labelled", "fitted"):
                assert blocks[id]["rows"] == 1, (id, blocks[id])
            assert celled["inside"] > 6 * celled["size"], celled
            assert kept["scrolls"] > 1 and kept["rows"] == 1, kept
            assert root_overflow(page) <= 0


def test_a_wrapped_row_hangs_from_its_line_s_indent_behind_a_mark(browser, serve):
    """Each line of a code block stands in a box of its own (readings/code-lines.js), so the
    rows a long line wraps onto start two columns past that line's own indent, and the
    first of those columns holds a mark on each of them, which a line that fits never
    shows (reading.css, `pre`). The boxes change no text: the block reads, selects and
    copies as its source, a selection in it survives the boxing, a line indented by a
    tab starts where one indented by spaces to the same column does, and its wrapped
    rows count the tab at the block's own `tab-size`. A block where an element holds a newline before its
    end stays as authored, its wrapped rows two columns from the block's edge, unmarked,
    and so does one whose `<code>` shares it with other text, which keeps its
    colouring."""
    long = "compute(value, retries=3, timeout=5000, backoff=2.5, jitter=True, report=False)"
    source = f"def run(value):\n    return {long}\n"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Wrapped rows",
                f"""<h1>Wrapped rows</h1>
<pre id="code"><code class="language-python">{source}</code></pre>
<pre id="crossed">short <mark>marked
and on</mark> {long}</pre>
<pre id="tabs"><code>\talpha
        beta
</code></pre>
<pre id="beside"><code class="language-python">print(1)</code>
</pre>
<pre id="narrow-tabs" style="tab-size: 4"><code>\t{long}
</code></pre>""",
            )
        ),
    )
    resized(page, 390, 844)
    lines = page.locator("#code [data-lf-pre-line]")
    expect(lines).to_have_count(2)
    read = r"""(line) => {
        const range = document.createRange();
        range.selectNodeContents(line);
        const rows = [...range.getClientRects()].filter((r) => r.width > 1);
        const tops = [...new Set(rows.map((r) => Math.round(r.top)))];
        const second = rows.find((r) => Math.round(r.top) === tops[1]);
        const one = document.createRange();
        const words = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
        let text = words.nextNode();
        while (text && !/\S/.test(text.data)) text = words.nextNode();
        const at = text.data.search(/\S/);
        one.setStart(text, at);
        one.setEnd(text, at + 1);
        const mark = getComputedStyle(line, '::before');
        return {
          rows: tops.length,
          hang: second ? (second.left - rows[0].left) / one.getBoundingClientRect().width : 0,
          mark: parseFloat(mark.left) / one.getBoundingClientRect().width,
          marked: parseFloat(mark.height) / parseFloat(getComputedStyle(line).lineHeight),
        };
    }"""
    first, wrapped = (lines.nth(0).evaluate(read), lines.nth(1).evaluate(read))
    assert first["rows"] == 1 and first["marked"] == 0, first
    assert wrapped["rows"] > 1, wrapped
    assert wrapped["hang"] == pytest.approx(6, abs=0.1), wrapped
    assert wrapped["mark"] == pytest.approx(4, abs=0.1), wrapped
    assert wrapped["marked"] == pytest.approx(wrapped["rows"] - 1, abs=0.05), wrapped
    assert page.locator("#code").evaluate(
        """(pre) => {
          const selection = getSelection();
          selection.selectAllChildren(pre);
          return [pre.textContent, selection.toString().replace(/\\n?$/, '\\n')];
        }"""
    ) == [source, source]
    assert page.locator("#tabs").evaluate(
        """(pre) => {
          const starts = [];
          const words = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
          for (let node; (node = words.nextNode()); ) {
            const at = node.data.search(/[a-z]/);
            if (at < 0) continue;
            const range = document.createRange();
            range.setStart(node, at);
            range.setEnd(node, at + 1);
            starts.push(Math.round(range.getBoundingClientRect().left));
          }
          return starts.length === 2 && starts[0] === starts[1];
        }"""
    ), "a tab-indented line should start where a space-indented one does"
    narrow = page.locator("#narrow-tabs [data-lf-pre-line]").evaluate(read)
    assert narrow["hang"] == pytest.approx(6, abs=0.1), narrow
    assert page.evaluate(
        """async () => {
              const {dressCode} = await window.__lfWidgetApi();
              const pre = document.createElement('pre');
              pre.textContent = 'first line\\nsecond line\\n';
              document.querySelector('#code').after(pre);
              const text = pre.firstChild;
              getSelection().setBaseAndExtent(text, 6, text, 17);
              const before = getSelection().toString();
              await dressCode(pre);
              return [before, getSelection().toString(),
                pre.querySelectorAll('[data-lf-pre-line]').length];
            }"""
    ) == ["line\nsecond", "line\nsecond", 2]
    expect(page.locator("#beside > code")).to_have_attribute("data-lf-syntax", "python")
    expect(page.locator("#beside [data-lf-pre-line]")).to_have_count(0)
    crossed = page.locator("#crossed")
    expect(crossed.locator("[data-lf-pre-line]")).to_have_count(0)
    assert crossed.evaluate(
        """(pre) => {
          const range = document.createRange();
          range.selectNodeContents(pre);
          const rows = [...range.getClientRects()].filter((r) => r.width > 1);
          const left = Math.min(...rows.map((r) => r.left));
          return rows.some((r) => r.left - left > 10);
        }"""
    ), "the crossed block's wrapped rows should hang from its edge"


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
                page.locator(".lf-fp-leaf").click()
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
  const parts = (value) => value.replace(/var\\((--lf-raise-\\d-(?:drop|blur))\\)/g,
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


# A box that spends --lf-shade, since the token itself is the same `light-dark()` text
# under either scheme.
PAINTED_SHADE = """() => {
  const probe = document.createElement('div');
  probe.style.color = 'var(--lf-shade)';
  document.body.append(probe);
  const ink = getComputedStyle(probe).color;
  probe.remove();
  return ink;
}"""


def test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink(
    browser, serve
):
    """A box stands at one of three heights, and only the theme spells them out.

    Lifts that each write their own geometry stand two menus beside each other at
    different heights for no reason anyone chose, and nothing keeps the next one from
    writing another. The `--lf-raise-*` tokens (tokens.css, beside --lf-shade) are the
    only declarations that write a blur; every other rule, a
    filter's drop-shadow() included, names one, with a hairline or ring beside it where
    its edge needs one.

    A drop shadow written as rgba(0,0,0,α) can only be right about one ground: at .12
    over the light paper a menu lifts its ground by 10 L*, and over the dark paper by
    1.4. So the heights are cast in --lf-shade, the ink stated once per scheme, and the two
    schemes are then asked for different answers from it.

    Asked of the declarations rather than of the paint, because that is where the fault
    is: "does this name the token" is exact, where a screenshot of a blurred edge is not.
    """
    page = open_page(browser, serve(LONG_PAGE))
    lifted = page.evaluate(ELEVATION_SHADOWS)
    heights = {s["property"] for s in lifted if s["property"].startswith("--lf-raise-")}
    assert heights == {"--lf-raise-1", "--lf-raise-2", "--lf-raise-3"}, (
        f"the layer spells the heights {sorted(heights)}, not --lf-raise-1 to --lf-raise-3: "
        f"this reading has stopped finding them and the assertions below are about "
        f"nothing"
    )
    spelled = [s for s in lifted if not s["property"].startswith("--lf-raise-")]
    assert not spelled, (
        f"{len(spelled)} lifts write their own geometry rather than naming a --lf-raise-* "
        f"height:\n  "
        + "\n  ".join(f"{s['said']} — {s['property']}: {s['value']}" for s in spelled)
    )
    raw = [s for s in lifted if "var(--lf-shade)" not in s["value"]]
    assert not raw, (
        f"{len(raw)} heights are cast in a colour of their own rather than in --lf-shade, "
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


# The WCAG contrast of an element's words, or of its edge, against the ground they stand
# on, each colour as the browser paints it.
CONTRAST = """([selector, property]) => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d', {willReadFrequently: true});
    const painted = (colour) => {
        context.fillStyle = colour;
        context.fillRect(0, 0, 1, 1);
        return [...context.getImageData(0, 0, 1, 1).data].slice(0, 3);
    };
    const luminance = (colour) => painted(colour)
        .map((channel) => channel / 255)
        .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    const element = document.querySelector(selector);
    let ground = element;
    while (getComputedStyle(ground).backgroundColor === 'rgba(0, 0, 0, 0)')
        ground = ground.parentElement;
    const [a, b] = [
        luminance(getComputedStyle(element)[property]),
        luminance(getComputedStyle(ground).backgroundColor),
    ].sort((x, y) => y - x);
    return (a + 0.05) / (b + 0.05);
}"""


# A word press and a field Leaf builds by role, as a widget builds them (`offerAction`,
# `offer`), into the page's `#controls`: Leaf's own controls, which wear their faces
# with a theme or without one.
LEAF_CONTROLS = """async () => {
    const {offerAction, offer} = await import("/runtime/lib/controls.js");
    const press = offerAction('word', '', 'Recompute');
    press.id = 'press';
    const field = offer('input', '', undefined, 'text');
    field.id = 'field';
    field.setAttribute('aria-label', 'Volume');
    document.getElementById('controls').append(press, ' ', field);
}"""

# What a control's face draws, as `getComputedStyle` names it.
FACE = (
    "el => Object.fromEntries(['paddingTop', 'paddingLeft', 'height', 'borderTopWidth',"
    " 'borderTopColor', 'borderTopLeftRadius', 'backgroundColor', 'color']"
    ".map(p => [p, getComputedStyle(el)[p]]))"
)


@pytest.mark.parametrize("reading", [True, False])
def test_a_theme_gives_a_page_s_own_controls_leaf_s_faces(browser, serve, reading):
    """Where the page's theme turns on markup's reading face, a bare button, a submit
    button, a pressed submit button and a text field the page writes wear the faces of
    Leaf's own word, commit, pressed commit and field (controls.css, "The faces of
    Leaf's control roles"), so the page's controls and Leaf's read as one set, and a
    label holding a checkbox at any depth is a choice whose ring stands on the label;
    a page that takes no theme keeps the browser's. A page taking these faces only by
    writing Leaf's class names, `lf-btn`, `lf-btn lf-commit`, `lf-field` and
    `lf-choice`, would leave a pressed submit button with the selected toggle's accent
    and a mark wrapped in a span with no face."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Own controls",
                '<h1>Own controls</h1><p id="controls"></p>'
                '<p><button id="own" type="button">Run all</button>'
                ' <button id="own-submit" type="submit">Generate</button>'
                ' <button id="own-done" type="submit" aria-pressed="true">Done</button>'
                ' <input id="own-field" type="text" aria-label="Name"></p>'
                '<p><label id="own-direct"><input type="checkbox">Include notes</label>'
                ' <label id="own-nested"><span><input id="own-mark" type="checkbox">'
                "</span>Include images</label></p>",
            ),
            reading=reading,
        ),
    )
    page.evaluate(LEAF_CONTROLS)
    page.evaluate("""async () => {
      const {offerAction} = await import("/runtime/lib/controls.js");
      const commit = offerAction('commit', '', 'Commit');
      commit.id = 'commit';
      const done = offerAction('commit', '', 'Done');
      done.id = 'done';
      done.setAttribute('aria-pressed', 'true');
      document.getElementById('controls').append(commit, done);
    }""")
    pairs = {
        "#own": "#press",
        "#own-submit": "#commit",
        "#own-done": "#done",
        "#own-field": "#field",
    }
    faces = {
        own: (page.locator(own).evaluate(FACE), page.locator(leaf).evaluate(FACE))
        for own, leaf in pairs.items()
    }
    for own, (drawn, leaf) in faces.items():
        if not reading:
            assert drawn["paddingLeft"] != leaf["paddingLeft"], (own, drawn)
        else:
            assert drawn == leaf, own
    mark = page.locator("#own-mark")
    style = "(el, p) => getComputedStyle(el)[p]"
    if not reading:
        assert mark.evaluate(style, "appearance") == "auto"
        return
    assert mark.evaluate(style, "appearance") == "none"
    nested, direct = page.locator("#own-nested"), page.locator("#own-direct")
    assert nested.evaluate(style, "paddingLeft") == direct.evaluate(
        style, "paddingLeft"
    )
    mark.click()
    page.keyboard.press("Space")
    rendered(page)
    assert nested.evaluate(style, "outlineStyle") == "solid"
    assert mark.evaluate(style, "outlineStyle") == "none"


@pytest.mark.parametrize("reading", [True, False])
def test_a_page_s_paper_and_ink_recolour_what_leaf_draws(browser, serve, reading):
    """A page states its ground and its text once, as `--lf-paper` and `--lf-ink`, and
    the neutral colours Leaf draws in step from the one toward the other
    (styles/tokens.css), with a theme or without one. Were each neutral a colour stated
    for the reading theme's paper, a dark page would keep them, and a control's quiet
    words and a field's edge would lose their contrast on it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Night shift",
                '<h1>Night shift</h1><p id="controls"></p>',
                head="<style>:root { color-scheme: dark; --lf-paper: #101828;"
                " --lf-ink: #e2e8f0; } html { background: var(--lf-paper); }</style>",
            ),
            reading=reading,
        ),
    )
    page.evaluate(LEAF_CONTROLS)
    words = page.evaluate(CONTRAST, ["#press", "color"])
    edge = page.evaluate(CONTRAST, ["#field", "borderTopColor"])
    assert words >= 4.5, f"a control's quiet words read {words:.2f}:1 on the page"
    assert edge >= 1.3, f"a field's edge reads {edge:.2f}:1 against its ground"


CODE_SURFACES = leaf_page(
    "Code surfaces",
    """<h1>Code surfaces</h1>
<lf-code id="code" hi="2"><pre><code class="language-python">def route(weather):
    return "terrace" if weather == "rain" else "courtyard"
</code></pre><lf-note at="1">Rain moves the party under cover.</lf-note></lf-code>
<pre id="plain"><code class="language-python">limit = 2  # doubled</code></pre>
<div style="color-scheme: dark"><pre id="panelled">limit = 3</pre></div>
<lf-text-document id="doc" label="change.diff" class="language-diff"><pre>@@ -1,2 +1,2 @@
-limit = 1
+limit = 2
</pre></lf-text-document>
<lf-text-document id="notes" label="notes.md" preview="markdown"><pre># Rollout

The canary runs for a day.
</pre></lf-text-document>
<lf-diff id="patch" view="patch"><pre>diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -1,1 +1,1 @@
-A = 1
+A = 2
</pre><lf-diff-note id="patch-note" file="x.py" side="new" at="1">The new value doubles it.</lf-diff-note></lf-diff>""",
)

# The WCAG contrast of each number, sign, note, caption and status ink on the page's
# code surfaces against the ground under it, each colour composited as the browser paints
# it, and the lightness of each code surface's canvas.
CODE_CONTRAST = """() => {
    const cx = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
    const paint = (layers) => {
        for (const colour of ['white', ...layers]) {
            cx.fillStyle = colour;
            cx.fillRect(0, 0, 1, 1);
        }
        return [...cx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
    };
    const luminance = (rgb) => rgb
        .map((c) => (c /= 255) <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    // The backgrounds under an element, its own included, outermost first.
    const grounds = (element) => {
        const ground = [];
        for (let at = element; at; at = at.parentElement ?? at.getRootNode().host)
            ground.unshift(getComputedStyle(at).backgroundColor);
        return ground;
    };
    const contrast = (element, {pseudo = null, card = null, ink = null} = {}) => {
        const ground = grounds(element);
        if (card) ground.push(getComputedStyle(element, card).backgroundColor);
        const [a, b] = [paint([...ground, ink ?? getComputedStyle(element, pseudo).color]),
            paint(ground)].map(luminance);
        return Math.round((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) * 100) / 100;
    };
    // A token as it resolves where the browser paints a highlight with it.
    const token = (element, name) => {
        const probe = element.appendChild(document.createElement('span'));
        probe.style.color = `var(${name})`;
        const colour = getComputedStyle(probe).color;
        probe.remove();
        return colour;
    };
    const diff = document.querySelector('#patch').shadowRoot;
    const row = document.querySelector('#doc .lf-text-document-run > *');
    const readings = [
        ...[...document.querySelectorAll('#code .lf-code-line')].map((line) =>
            [`code line ${line.dataset.lfLine}'s number`, contrast(line, {pseudo: '::before'})]),
        ['the highlighted line', contrast(document.querySelector('#code [data-lf-hi]'))],
        ['the code note', contrast(document.querySelector('#code lf-note'))],
        ['the document caption', contrast(document.querySelector('#doc figcaption'))],
        ["a document line's number", contrast(row, {pseudo: '::before'})],
        ['an added document line', contrast(row, {ink: token(row, '--lf-ok-ink')})],
        ['a removed document line', contrast(row, {ink: token(row, '--lf-danger-ink')})],
        ...[...diff.querySelectorAll('.lf-diff-line-number')].map((number) =>
            [`diff number ${number.textContent}`, contrast(number)]),
        ...[...diff.querySelectorAll('[data-line-type^="change-"]')].map((line) =>
            [`${line.dataset.lineType} sign`, contrast(line, {pseudo: '::before'})]),
        ...[...diff.querySelectorAll('.lf-diff-additions, .lf-diff-deletions')].map(
            (count) => [count.className, contrast(count)]),
        ['the diff note', contrast(diff.querySelector('lf-diff-note'), {card: '::after'})],
    ];
    // Each surface's canvas: a plain block, lf-code's, a document's listing, a
    // previewed document's Source tab, which the preview's height sets, and a diff's rows.
    const canvases = Object.fromEntries([
        ['plain', document.querySelector('#plain')],
        ['lf-code', document.querySelector('#code pre')],
        ['listing', document.querySelector('#doc .lf-text-document-listing > pre')],
        ['source tab', document.querySelector('#notes lf-tab:has(> .lf-text-document-listing)')],
        ['diff rows', diff.querySelector('.lf-diff-file > details')],
    ].map(([name, element]) =>
        [name, luminance(paint([getComputedStyle(element).backgroundColor]))]));
    // Each block's Copy: the plain block's, which its hover shows in chrome, out of the
    // block, and the one on lf-code's toolbar, beside its source.
    const copies = Object.fromEntries([
        ['plain', document.querySelector('.lf-block-controls .lf-code-copy')],
        ['lf-code', document.querySelector('#code > .lf-code-bar .lf-code-copy')],
    ].map(([name, element]) => [name, luminance(paint(grounds(element)))]));
    return {
        canvases,
        copies,
        // A block in a part of the page its author drew dark.
        panelled: luminance(paint([
            getComputedStyle(document.querySelector('#panelled')).backgroundColor])),
        read: readings.length,
        unread: readings.filter(([, ratio]) => ratio < 4.5),
    };
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_theme_draws_its_code_in_the_scheme_it_names(request, serve, engine):
    """A theme or page sets `--lf-code-scheme` to draw code in a scheme of its own, as
    dark code on a light page (package-themes.md, "Theme tokens"). Every code surface
    takes that scheme's branch of each token inside it, so every number, sign, note,
    caption, highlighted line and status ink reads at 4.5:1 or more against its ground,
    and the syntax probe finds nothing. Unset, the code takes the scheme of what holds
    it, a part of the page its author drew dark included. While a
    theme could only restate the code tokens dark, the page's status inks, its muted
    words and the highlight's tint stayed light: a diff's changed line numbers read
    2.2:1, a note on a diff 1.1:1 and a highlighted line 1.2:1."""
    page = open_page(request.getfixturevalue(engine), serve(CODE_SURFACES))
    page.locator("#plain").hover()
    rendered(page)
    light = page.evaluate(CODE_CONTRAST)
    # A surface that drew no numbers, signs or counts leaves the readings short.
    assert light["read"] >= 15, f"only {light['read']} readings: the page drew less"
    light_canvases = {
        name: lum for name, lum in light["canvases"].items() if lum <= 0.9
    }
    assert not light_canvases, (
        f"code took a scheme the page doesn't have: {light_canvases}"
    )
    assert light["unread"] == [], light["unread"]
    assert light["panelled"] < 0.05, "code left the scheme the page set around it"
    page.evaluate(
        "() => document.documentElement.style.setProperty('--lf-code-scheme', 'dark')"
    )
    rendered(page)
    dark = page.evaluate(CODE_CONTRAST)
    lit = {name: lum for name, lum in dark["canvases"].items() if lum >= 0.05}
    assert not lit, f"the code scheme never reached these canvases: {lit}"
    assert dark["unread"] == [], dark["unread"]
    light_copies = {name: lum for name, lum in dark["copies"].items() if lum >= 0.1}
    assert not light_copies, f"Copy stayed a light control on dark code: {light_copies}"
    assert evaluate_probe(page, "unreadSyntax") == []


# A framework's reset in the layer Tailwind keeps it in, beside the author's own base
# rules.
RESET = (
    "@layer base { *, ::before, ::after { margin: 0; padding: 0; border: 0 solid; }"
    " button, input { background: transparent; border-radius: 0; font: inherit;"
    " color: inherit; } }"
)
