"""Selection, passage, syntax, and version-travel tests."""

import json
import re
from html import escape

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, record_claim
from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import passages as passages_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_layout import (
    banner_control,
)
from render_cases_navigation import (
    _publish,
    source_revision,
)
from render_harness import (
    EXAMPLES,
    INLINE_PAGE,
    PASSAGE_SOURCES,
    RELEASE_FOCUS,
    command_reference_rows,
    compare_with,
    hold_selection,
    leaf_page,
    open_page,
    open_versions,
    panel_settled,
    resized,
    scroll_settled,
    sending,
    shortcut_bar_text,
    ticked,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_anchors import open_selected_comment


@pytest.mark.parametrize("source", PASSAGE_SOURCES, ids=lambda source: source.stem)
def test_real_page_passages_can_be_quoted(browser, serve, source):
    """Passages in four unlike authored pages are quotable.

    A passage's shape is what has made selection and search come apart: its block,
    the widgets around it, whether the runtime says it, and the text transform and
    white space it is set in. The sweep drags once across each shape the page holds,
    and once across each pair of shapes that stand next to each other; a repeat of a
    shape it has already dragged across adds time and no evidence.

    Focused tests own settlements, tabs, shadow roots, and gestures.
    """
    page = open_page(browser, serve(source))
    # A user reaches everything eventually — opens the details, clicks through to the
    # other tab — so everything is in scope, not just what the page opens on. The page's
    # own content, not the chrome, whose runtime owns what it shows.
    page.evaluate("""() => {
        const own = el => !el.closest('.lf-ui');
        document.querySelectorAll('details').forEach(d => {
            if (own(d)) d.toggleAttribute('open', true);
        });
        document.querySelectorAll('[hidden]').forEach(e => {
            if (own(e)) e.removeAttribute('hidden');
        });
    }""")
    # What the reveal brings into view finishes arriving before the sweep reads it, as it
    # does before a user can select it: a chart in a shut tab draws only once it has a
    # box, and its drawing replaces the source a sweep that started first had counted.
    rendered(page)
    wait_until_ready(page)
    result = page.evaluate(
        """async () => {
        const {pageRange} = await window.__lfRuntimeImport('/runtime/passages.js');
        const {TEXT_BLOCK} = await window.__lfRuntimeImport('/runtime/passage-facts.js');
        const {anchorForRange, resolveAnchor} =
            await window.__lfRuntimeImport('/runtime/anchor-resolution.js');
        const {nextRender, renderingState} =
            await window.__lfRuntimeImport('/runtime/rendering.js');
        const tick = () => new Promise(r => setTimeout(r, 0));
        const rendered = async () => {
            let timer;
            const deadline = new Promise((_, reject) => {
                timer = setTimeout(() => reject(
                    new Error('Selection rendering did not settle')), 10000);
            });
            try {
                await Promise.race([deadline, (async () => {
                    await tick();
                    await new Promise(resolve => nextRender(resolve));
                    while (!Object.values(renderingState()).every(Boolean)) await tick();
                })()]);
            } finally {
                clearTimeout(timer);
            }
        };
        // The composer's field joins the page at its first open.
        const fab = () => document.querySelector('.lf-fab-input');
        const speaks = el => {
            const near = el.closest('.lf-ui, [data-lf-said]');
            return !near || near.matches('[data-lf-said]');
        };
        // Native passage blocks come from the runtime. The composite roots are
        // representative widgets whose direct prose otherwise has no native block;
        // data-lf-said is the runtime's marker for generated words the page still says.
        const compositeSelector = 'lf-option,lf-sample';
        const blocks = [...document.querySelectorAll(
            `${TEXT_BLOCK},${compositeSelector},[data-lf-said]`)]
          .filter(b => speaks(b) && b.checkVisibility()
                    && b.textContent.trim().length > 12);
        const shape = block => {
            const style = getComputedStyle(block);
            const widgets = [];
            for (let el = block.parentElement; el; el = el.parentElement)
                if (el.localName.includes('-')) widgets.push(el.localName);
            return [block.localName, block.hasAttribute('data-lf-said'),
                    style.textTransform, style.whiteSpace, ...widgets].join(' ');
        };
        // Each shape alone, then reaching into the next block — a drag rarely stops
        // tidily on a boundary, and spanning two blocks is where the joins show.
        const drags = new Map();
        blocks.forEach((block, i) => {
            const next = blocks[i + 1];
            drags.set(shape(block), drags.get(shape(block)) ?? [block, block]);
            if (next) {
                const join = `${shape(block)} | ${shape(next)}`;
                drags.set(join, drags.get(join) ?? [block, next]);
            }
        });
        const missed = [], skipped = [], astray = [], nonexact = [];
        let attempted = 0, detached = 0, fallback = 0;
        for (const [start, end] of drags.values()) {
            attempted++;
            // A mouse selection starts in page words and ends with the native
            // pointer/mouse release pair; selectionchange alone does not snap.
            const pointer = {bubbles: true, composed: true, isPrimary: true,
                             pointerType: 'mouse', button: 0};
            start.dispatchEvent(new PointerEvent('pointerdown', pointer));
            let range = document.createRange();
            range.setStart(start, 0);
            range.setEnd(end, end.childNodes.length);
            const sel = getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            end.dispatchEvent(new PointerEvent('pointerup', pointer));
            end.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            await rendered();
            // Mouse release snaps the native selection to word and sentence edges.
            // The mark must match the selection the reader now sees.
            range = pageRange(sel);
            // Counted, not shrugged off: a selection the button declines to offer is
            // a passage silently outside this sweep, and the sweep is the coverage.
            if (fab()?.style.display !== 'block') {
                skipped.push(range.toString().replace(/\\s+/g, ' ').trim().slice(0, 70));
                continue;
            }
            const anchor = anchorForRange(range);
            const resolved = resolveAnchor(anchor);
            // A cross-cell selection remains a real native selection and a writable
            // comment. It must not acquire an exact semantic highlight by ignoring
            // the same fences file capture respects. Generated wordless faces and
            // identified data can also retain an element fallback.
            if (!resolved?.exact || resolved.kind !== 'passage') {
                nonexact.push(anchor);
                if (anchor.detached) detached++;
                else fallback++;
                if (range.collapsed || !range.toString().trim() || fab.disabled)
                    missed.push('unusable native selection: ' + range.toString().slice(0, 70));
                sel.removeAllRanges();
                await rendered();
                continue;
            }
            const painted = CSS.highlights.get('lf-pending');
            // The captured quote, read off the node whether or not the user can
            // see it: the composer shows it only where the page has no mark to give,
            // which is the very case this loop is counting.
            const quoted = document.getElementById('lf-composer-quote').textContent;
            if (!painted || ![...painted].map(r => r.toString()).join('').trim())
                missed.push(quoted.slice(0, 70));
            // Inside what was selected, not merely somewhere: a matcher that finds
            // the right words in the wrong place paints, and paints a lie.
            //
            // A mark can now land inside a widget's shadow tree (x-shadow), and two
            // ranges in different trees cannot be compared at all — comparing them
            // throws rather than answering. So the question crosses the way the
            // runtime's own does: the tree renders where its host stands, so a mark
            // inside one is inside the selection exactly when the host is.
            else if ([...painted].some(p => {
                    const root = range.commonAncestorContainer.getRootNode();
                    if (p.startContainer.getRootNode() === root)
                        return p.compareBoundaryPoints(Range.START_TO_START, range) < 0
                            || p.compareBoundaryPoints(Range.END_TO_END, range) > 0;
                    let n = p.startContainer;
                    while (n && n.getRootNode() !== root) n = n.getRootNode().host;
                    return !n || !range.intersectsNode(n);
                }))
                astray.push(quoted.slice(0, 70));
            // The next drag reads the Comment field's state afresh only once this
            // selection's composer has closed; the rest of the page's rendering
            // settles before that drag is read.
            sel.removeAllRanges();
            for (let i = 0; fab()?.style.display === 'block' && i < 1000; i++) await tick();
            if (fab()?.style.display === 'block')
                missed.push('Comment stayed open once the selection cleared');
        }
        return {attempted, detached, fallback, missed, skipped, astray, nonexact};
    }"""
    )
    # Refusing a highlight needs evidence independent of browser resolution. A
    # regression that detaches ordinary file-readable prose must fail this sweep.
    passages = passages_model.page_passages(
        structure_model.SourceDocument((serve.page_dir / "index.html").read_text()),
        json.loads((serve.page_dir / "registry.json").read_text()),
    )
    for anchor in result["nonexact"]:
        located = {key: value for key, value in anchor.items() if key != "detached"}
        assert anchor_capture_model.resolve_quote(passages, located) is None, (
            f"{source.stem}: browser detached a file-readable passage: {anchor}"
        )
    assert result["attempted"] > 0, f"{source.stem}: the passage sweep found nothing"
    assert result["missed"] == [], (
        f"{len(result['missed'])} passages in {source.stem} quote text the page "
        f"can't find: {result['missed']}"
    )
    assert result["skipped"] == [], (
        f"{len(result['skipped'])} passages in {source.stem} raised no Comment button, "
        f"so this sweep never tested them: {result['skipped']}"
    )
    assert result["astray"] == [], (
        f"{len(result['astray'])} passages in {source.stem} painted outside what was "
        f"selected: {result['astray']}"
    )


def test_a_block_leaving_the_viewport_keeps_its_focused_comment(browser, serve):
    """A block scrolling out of view gives the viewport its draft before it loses focus."""
    source = next(source for source in EXAMPLES if source.stem == "live-progress")
    page = open_page(browser, serve(source))
    resized(page, 700, 850)
    page.evaluate("""() => {
        const range = document.createRange();
        range.selectNodeContents(document.querySelector('#lp-k-checks'));
        getSelection().removeAllRanges();
        getSelection().addRange(range);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    field = page.locator(".lf-fab-input")
    page.keyboard.press("c")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    label = field.get_attribute("aria-label")
    assert label and label.startswith("Comment on “checks passing 4 of 5")
    draft = "Why does the remaining check need a decision?"
    write(field, draft)
    resized(page, 420, 850)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)

    # Native End on macOS scrolls the page even from a text box. A smooth scroll can
    # cross this narrow band in one frame or several; put that actual geometry on screen
    # directly so the test cannot miss the point where the region no longer fits a field.
    page.locator("#lp-status").evaluate(
        "region => window.scrollTo(0, scrollY + region.getBoundingClientRect().bottom - 20)"
    )
    rendered(page)
    assert page.locator("#lp-status").evaluate(
        "region => Math.abs(region.getBoundingClientRect().bottom - 20) < 1"
    )
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-label", label)
    page.keyboard.type(" What must Finance decide?")
    expect(field).to_have_js_property("value", draft + " What must Finance decide?")


def test_code_copy_keeps_source_and_stays_beside_scrolling_and_revised_blocks(
    browser, serve
):
    """Copy uses source, including whitespace, rather than rendered annotations.

    A numbered widget and both ordinary block shapes share the same gesture.
    The retained widget's Copy returns after a hidden widget is detached and
    reconnected. The control stays reachable beside horizontally scrolling code,
    and a revision updates its source or removes it without duplicating controls.
    """
    colored = '\n  print("' + "long source " * 30 + '")\t\n'
    suffix = "VISIBLE_END"
    plain = "dense_source_" * 30 + suffix
    widget = 'def greet():\n    return "hello"'

    def document(colored_source=colored, plain_source=plain, *, keep_colored=True):
        return leaf_page(
            "copy source",
            '<h1 id="title">Copy source</h1>'
            + (
                '<pre id="colored" style="anchor-name: --authored-colored, --authored-secondary">'
                '<code class="language-python">'
                + escape(colored_source)
                + "</code></pre>"
                if keep_colored
                else ""
            )
            + '<pre id="plain" tabindex="0"><code>'
            + escape(plain_source)
            + '</code></pre><a id="after-copy" href="#title">After code</a>'
            + '<lf-code id="numbered" language="python" hi="2"><pre>'
            + escape(widget)
            + '</pre><lf-note at="2">This annotation is not source.</lf-note></lf-code>'
            + '<lf-draft id="draft"><pre>Non-code data has no copy control.</pre></lf-draft>',
            head="<style>#plain { anchor-name: --authored-plain; }"
            "#numbered.lf-rendered > pre { anchor-name: --authored-numbered; }</style>",
        )

    url = live_url(serve(document()))
    page = open_page(browser, url)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    controls = page.locator(".lf-code-copy")
    expect(controls).to_have_count(3)
    document_controls = page.locator(".lf-chrome > .lf-code-copy")
    expect(document_controls).to_have_count(2)
    expect(page.locator("#colored")).to_have_attribute("tabindex", "0")
    expect(page.locator("#colored")).to_have_attribute("aria-keyshortcuts", "Enter")
    expect(page.locator("#numbered lf-note")).to_contain_text("not source")
    expect(page.locator("#numbered .lf-quiet")).to_have_count(1)

    anchors = {}
    for block, control in (
        ("colored", document_controls.nth(0)),
        ("plain", document_controls.nth(1)),
        ("numbered", page.locator("#numbered > .lf-code-copy")),
    ):
        anchors[block] = control.evaluate(
            """(copy, selector) => {
              const pre = document.querySelector(selector);
              return {
                names: getComputedStyle(pre).anchorName.split(',').map(name => name.trim()),
                copyAnchor: getComputedStyle(copy).positionAnchor,
              };
            }""",
            f"#{block}" if block != "numbered" else "#numbered > pre",
        )
    authored = {
        "colored": {"--authored-colored", "--authored-secondary"},
        "plain": {"--authored-plain"},
        "numbered": {"--authored-numbered"},
    }
    for block, reading in anchors.items():
        assert authored[block].issubset(reading["names"]), anchors
        assert reading["copyAnchor"] in reading["names"], anchors

    def copy(pre_selector, control, expected, *, keyboard=False):
        button = control.get_by_role("button")
        pre = page.locator(pre_selector)
        expect(button).to_have_attribute("aria-label", "Copy code")
        pre.scroll_into_view_if_needed()
        page.mouse.move(0, 0)
        page.evaluate(RELEASE_FOCUS)
        expect(control).to_have_css("opacity", "0")

        def geometry():
            return control.evaluate(
                """(copy, selector) => {
                  const pre = document.querySelector(selector);
                  const source = pre.querySelector('code') ?? pre.querySelector('.lf-code-line');
                  const range = new Range();
                  range.selectNodeContents(source);
                  const rect = box => [box.x, box.y, box.width, box.height];
                  return {
                    padding: getComputedStyle(pre).paddingTop,
                    frame: rect(pre.getBoundingClientRect()),
                    source: rect(range.getClientRects()[0]),
                    button: rect(copy.shadowRoot.querySelector('button').getBoundingClientRect()),
                  };
                }""",
                pre_selector,
            )

        before = geometry()
        assert before["padding"] == "12px", before
        frame, overlay = before["frame"], before["button"]
        assert 0 <= overlay[1] - frame[1] <= 8, before
        assert 0 <= frame[0] + frame[2] - overlay[0] - overlay[2] <= 8, before
        if keyboard:
            # Enter on the source copies it, though the control stands outside
            # authored markup and the Tab sequence. The register names that press
            # wherever it names keys: the shortcut bar, the command reference and
            # the block's aria-keyshortcuts.
            pre.focus()
            assert "copy code" in shortcut_bar_text(page)
            expect(pre).to_have_attribute("aria-keyshortcuts", "Enter")
            page.keyboard.press("?")
            page.keyboard.press("?")
            expect(
                command_reference_rows(page, "On a code block").get_by_text(
                    "Copy this block's code to the clipboard"
                )
            ).to_be_visible()
            page.keyboard.press("Escape")
            expect(pre).to_be_focused()
        else:
            pre.hover()
            expect(control).to_have_css("opacity", "1")
            button.hover()
        expect(control).to_have_css("opacity", "1")
        after = geometry()
        for box in ("frame", "source", "button"):
            assert after[box] == pytest.approx(before[box], abs=0.5), (before, after)
        if keyboard:
            page.keyboard.press("Enter")
            expect(pre).to_be_focused()
        else:
            button.click()
        expect(button).to_have_attribute("aria-label", "Code copied")
        expect(page.locator(".lf-notice")).to_have_text("Code copied")
        assert page.evaluate("navigator.clipboard.readText()") == expected

    copy("#colored", document_controls.nth(0), colored)
    # Make this block itself scrollable, so Tab has a known native starting stop.
    resized(page, 360, 900)
    copy("#plain", document_controls.nth(1), plain, keyboard=True)
    page.keyboard.press("Tab")
    expect(page.locator("#after-copy")).to_be_focused()
    widget_copy = page.locator("#numbered > .lf-code-copy")
    page.evaluate("document.querySelector('#numbered').style.display = 'none'")
    expect(widget_copy).to_have_css("display", "none")
    page.evaluate(
        "window.detachedCodeWidget = document.querySelector('#numbered'); detachedCodeWidget.remove()"
    )
    rendered(page)
    page.evaluate("""() => {
      document.querySelector('#draft').before(detachedCodeWidget);
      detachedCodeWidget.style.removeProperty('display');
    }""")
    copy("#numbered > pre", widget_copy, widget)

    pre = page.locator("#colored")
    pre.scroll_into_view_if_needed()
    assert pre.evaluate("el => el.scrollWidth > el.clientWidth")
    control = document_controls.nth(0)
    before = control.bounding_box()
    assert before
    pre.focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function("document.querySelector('#colored').scrollLeft > 0")
    scroll_settled(page)
    after = control.bounding_box()
    block = pre.bounding_box()
    assert after and block
    assert after["x"] == pytest.approx(before["x"], abs=1)
    assert block["x"] <= after["x"]
    assert after["x"] + after["width"] <= block["x"] + block["width"]

    revised = colored.replace("print", "display")
    _publish(serve.page_dir, 2, document(revised), "Revise copied source")
    wait_for_revision(page, 2)
    expect(controls).to_have_count(3)
    copy("#colored", document_controls.nth(0), revised)
    _publish(serve.page_dir, 3, document(keep_colored=False), "Remove copied block")
    wait_for_revision(page, 3)
    expect(controls).to_have_count(2)
    copy("#plain", document_controls.first, plain)

    # A renderer can keep the pre while changing what it holds. Leaving the code
    # shape must retire its generated control just as removing the pre does.
    page.locator("#plain").evaluate("pre => pre.replaceChildren('ordinary text')")
    expect(page.locator("#plain > code")).to_have_count(0)
    expect(document_controls).to_have_count(0)
    expect(page.locator("#plain")).not_to_have_attribute("aria-keyshortcuts")
    expect(controls).to_have_count(1)

    restored = "\n  restored_source()\t\n"
    page.locator("#plain").evaluate(
        """(pre, source) => {
          const code = document.createElement('code');
          code.textContent = source;
          pre.replaceChildren(code);
        }""",
        restored,
    )
    expect(document_controls).to_have_count(1)
    expect(controls).to_have_count(2)
    copy("#plain", document_controls.first, restored)

    touch_context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    touch = open_page(browser, url, context=touch_context)
    touch_control = touch.locator(".lf-chrome > .lf-code-copy")
    touch_button = touch_control.get_by_role("button")
    expect(touch_control).to_have_css("opacity", "1")
    expect(touch_button).to_have_accessible_name("Copy code")
    expect(touch.locator("#plain")).to_have_css("padding-top", "12px")
    hit = touch_button.bounding_box()
    assert hit and hit["width"] >= 44 and hit["height"] >= 44, hit
    touch_button.tap()
    expect(touch_button).to_have_accessible_name("Code copied")
    assert touch.evaluate("navigator.clipboard.readText()") == plain
    touch_pre = touch.locator("#plain")
    frame = touch_pre.bounding_box()
    touch_pre.tap(position={"x": 20, "y": 20})
    expect(touch_pre).to_be_focused()
    expect(touch_pre).to_have_attribute("tabindex", "0")
    expect(touch_control).to_have_css("opacity", "0")
    expect(touch_control).to_have_css("pointer-events", "none")
    assert touch_pre.bounding_box() == frame

    # The source owns a finger's horizontal swipe, even though the copy control
    # initially occupied its first line. Focus must not cancel the native scroll.
    cdp = touch_context.new_cdp_session(touch)
    assert frame
    x, y = frame["x"] + frame["width"] - 60, frame["y"] + 20
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]},
    )
    for step in range(1, 15):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [{"x": x - 240 * step / 14, "y": y}],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    touch.wait_for_function("document.querySelector('#plain').scrollLeft > 0")
    scroll_settled(touch)
    touch_pre.evaluate("pre => pre.scrollLeft = pre.scrollWidth")

    def select_suffix():
        reading = touch_pre.evaluate(
            """(pre, suffix) => {
          const text = pre.querySelector('code').firstChild;
          const range = new Range();
          range.setStart(text, text.length - suffix.length);
          range.setEnd(text, text.length);
          const rect = range.getBoundingClientRect();
          const copy = document.querySelector('.lf-chrome > .lf-code-copy');
          const hit = document.elementFromPoint(rect.right - 2, rect.top + rect.height / 2);
          return {opacity: getComputedStyle(copy).opacity,
                  covered: hit === copy || copy.contains(hit),
                  suffix: range.toString(),
                  start: [rect.left, rect.top + rect.height / 2],
                  end: [rect.right, rect.top + rect.height / 2],
                  frame: [pre.getBoundingClientRect().left, pre.getBoundingClientRect().right]};
        }""",
            suffix,
        )
        assert reading["opacity"] == "0" and not reading["covered"], reading
        assert reading["suffix"] == suffix
        assert reading["frame"][0] < reading["start"][0]
        assert reading["end"][0] < reading["frame"][1]
        hold_selection(touch, reading["start"], reading["end"])
        assert touch.evaluate("window.getSelection().toString()") == suffix
        touch.mouse.up()

    select_suffix()
    touch.locator("#title").tap()
    expect(touch_control).to_have_css("opacity", "1")
    expect(touch_control).to_have_css("pointer-events", "auto")
    expect(touch_pre).to_have_attribute("tabindex", "0")

    # A fitting dense line has the same reading route: its final characters must
    # stay available even though they sit beneath the resting copy control.
    fitting = touch_pre.evaluate(
        """(pre, suffix) => {
          const code = pre.querySelector('code');
          const range = new Range();
          range.setStart(code.firstChild, 0);
          range.setEnd(code.firstChild, 1);
          const width = range.getBoundingClientRect().width;
          const style = getComputedStyle(pre);
          const available = pre.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          return 'x'.repeat(Math.floor(available / width) - suffix.length) + suffix;
        }""",
        suffix,
    )
    touch.locator("#plain > code").evaluate(
        "(code, source) => code.textContent = source", fitting
    )
    assert touch_pre.evaluate("pre => pre.scrollWidth === pre.clientWidth")
    # The old scroll-state container query's 8px bottom float can survive the
    # text write for a rendering pass after the line itself stops overflowing.
    # Take geometry only after that old scrollbar clearance has gone.
    touch.wait_for_function(
        "getComputedStyle(document.querySelector('#plain'), '::after').content === 'none'"
    )
    frame = touch_pre.bounding_box()
    touch_pre.tap(position={"x": 20, "y": 20})
    expect(touch_pre).to_be_focused()
    select_suffix()
    touch.locator("#title").tap()
    expect(touch_control).to_have_css("opacity", "1")
    touch_pre.tap(position={"x": 20, "y": 20})
    expect(touch_control).to_have_css("opacity", "0")
    # The control refuses a second copy until its last result has shown.
    expect(touch_button).to_have_accessible_name("Copy code")
    touch.keyboard.press("Enter")
    expect(touch_button).to_have_accessible_name("Code copied")
    assert touch.evaluate("navigator.clipboard.readText()") == fitting
    expect(touch_pre).to_be_focused()
    expect(touch_pre).to_have_attribute("tabindex", "0")
    assert touch_pre.bounding_box() == frame

    # A wrapping widget has no authored stop to retain. Its touch focus is lent
    # for the reading gesture and disappears when the user leaves its source.
    numbered_pre = touch.locator("#numbered > pre")
    assert numbered_pre.get_attribute("tabindex") is None
    numbered_pre.tap(position={"x": 20, "y": 20})
    expect(numbered_pre).to_be_focused()
    expect(touch.locator("#numbered > .lf-code-copy")).to_have_css("opacity", "0")
    touch.locator("#title").tap()
    expect(numbered_pre).not_to_have_attribute("tabindex")
    expect(touch.locator("#numbered > .lf-code-copy")).to_have_css("opacity", "1")


def test_a_revised_example_travels_between_its_own_versions(browser, serve):
    """The corpus's own reading of version travel, on the one example that was revised.

    Every other version fixture publishes a second version out of one markup string,
    which is a page nobody wrote: the two documents differ by whatever the fixture
    edited, and what a user would see marked is whatever that edit happened to be.
    The shipped example is an authored pair — a proposal and the version that answered
    a comment on it — so what the comparison marks here is what a revision is: the
    paragraph rewritten around the sentence the user quoted, the paragraph and
    step it grew, and the title and lede updated to state the exception. Everything
    the revision left alone stays unmarked, including the
    section the other thread stands on, and both threads stay attached because both
    quotes survived.

    That is also this file's floor for the corpus. The example sweeps serve the newest
    version and never press anything, so with no reading here the picker could offer
    a list nobody walks and a Compare control nobody presses on every page in examples/."""
    example = next(p for p in EXAMPLES if p.stem == "log-retention")
    page = open_page(browser, serve(example))

    # Served at the newest version, with the earlier one behind the picker.
    expect(page.locator(".lf-version")).to_have_text("Showing v2")
    expect(page.locator(".lf-version-menu .lf-version-row")).to_have_count(2)

    compare_with(page, 1)
    expect(page.locator("main .lf-ins-block")).to_have_count(5)
    marked = page.eval_on_selector_all(
        "main .lf-ins-block", "els => els.map(e => e.id).sort()"
    )
    assert marked == [
        "ret-cost-body",
        "ret-cost-keep",
        "ret-lede",
        "ret-steps-carve",
        "ret-title",
    ], marked
    # A Change margin entry's press says what it reached, in the notice slot: its target is
    # usually on screen already, so the scroll moves nothing and a press that only spoke
    # to the live region was, to a sighted user, a press that did nothing. What the
    # press also discloses is the next test's; this one holds it to naming its target.
    page.locator(
        '.lf-margin-entry:has(svg[data-lf-icon="change"]):visible'
    ).first.click()
    expect(page.locator(".lf-notice")).to_have_text(
        re.compile(r"^[a-z ]+ changed since v1\b")
    )

    # The threads the log opened, both still on their passages: one on a block the
    # revision rewrote, one on a block it never touched.
    expect(page.locator(".lf-thread")).to_have_count(2)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)
    painted = re.sub(
        r"\s",
        "",
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => r.toString()).join('')"
        ),
    )
    for quote in (
        "Two years of incident write-ups name a log older than six weeks exactly twice.",
        (
            "Across eighteen months of query history, 90% of reads touch logs less than "
            "a week old and 95% stay within 42 days."
        ),
    ):
        assert re.sub(r"\s", "", quote) in painted, painted[:160]

    # And the older document is a real destination, not just a row: choosing it pins
    # the user to the virtual version address the picker named.
    banner_control(page, ".lf-version").click()
    page.locator('.lf-version-row[data-lf-version="1"]').click()
    page.wait_for_url(re.compile(r"/versions/v1\.html"))
    expect(page.locator(".lf-version")).to_have_text("Showing v1")
    expect(page.locator("#ret-cost-keep")).to_have_count(0)


def test_the_menu_runs_in_descending_number_order_past_v9(browser, serve):
    """A version stays an integer from the server through runtime state; only the
    menu and URL boundary render its file name. Order the versions by those names
    instead and v10 lands between v1 and v2: the menu reads out of sequence,
    the diff offers the wrong base, and a user on the newest version is told a
    newer one is waiting."""
    url = serve(INLINE_PAGE)
    for n in range(2, 11):
        _publish(serve.page_dir, n, INLINE_PAGE, f"cut {n}")
    page = open_page(browser, url.replace("v1.html", "v10.html"))

    # The menu is built whether or not it is open, so the order is readable without
    # a press — and the press is not what this test is about.
    rows = page.locator(".lf-version-menu .lf-version-row .lf-version-num")
    expect(rows).to_have_count(10)
    assert [t.split(" ")[0] for t in rows.all_text_contents()] == [
        f"v{n}" for n in range(10, 0, -1)
    ]
    expect(rows.first).to_have_text("v10 (latest version)")
    # The bases a diff can run against are every version older than this one, so the
    # first press in the menu is v9 — which is what "the version before this" comes to
    # once the ordering has decided it.
    presses = page.locator(".lf-version-diff")
    expect(presses).to_have_count(9)
    expect(presses.first).to_have_attribute("data-lf-version", "9")
    compare_with(page)
    expect(page.locator(".lf-version")).to_have_attribute(
        "title", re.compile(r"changed since v9 ")
    )
    # Nothing is newer than v10, so no chip offers one.
    expect(page.locator(".lf-latest-chip")).to_be_hidden()
    expect(page.locator(".lf-version")).not_to_have_attribute(
        "data-lf-news", re.compile(r".*")
    )
    page.close()

    # Pinned to the oldest, the chip naming the newest is the runtime's one place
    # that spells a version out in a sentence.
    page = open_page(browser, url, pin=True)
    expect(page.locator(".lf-latest-chip")).to_have_text(
        "New page available → open v10"
    )
    expect(page.locator(".lf-version")).to_have_attribute("data-lf-news", "")
    expect(page.locator(".lf-version")).to_have_attribute(
        "aria-label", "v1: open versions; v10 available"
    )


def test_a_row_the_platform_activates_names_both_of_its_keys(browser, serve):
    """A `<button>` is activated by Enter and by Space, and a row that says so by hand can
    say half of it. This one did: the version menu's row carries no `run` — the platform
    does the activating, and clicking behind it would be a second activation — so its keys
    are a description of what the browser will do, and the description read `⏎` while the
    control answered both. Nothing failed; the page under-promised a key that worked, which
    is the register's own failure wearing its quietest form.

    So the pair is one exported fact (`PRESS`) and the four rows that named it by hand read
    it: the runtime's control scope, a card grip in both its states, and this row. A link is
    what keeps that fact honest rather than growing into "controls answer two keys" — Enter
    follows an `<a>` and Space scrolls the page, so the leaves drawer binds Enter alone and is
    right to."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "second")

    # A comparison checkbox is the menu's internal Tab stop rather than part of its
    # arrow-key row walk. Reaching it must not be mistaken for leaving the popup.
    compared = open_page(browser, url.replace("/v1.html", "/v2.html"))
    open_versions(compared)
    compared.locator('.lf-version-row[data-lf-version="1"]').focus()
    compared.keyboard.press("Tab")
    comparison = compared.locator('.lf-version-diff[data-lf-version="1"]')
    expect(comparison).to_be_focused()
    expect(compared.locator(".lf-version-menu")).to_be_visible()
    expect(compared.locator(".lf-shortcut-bar")).to_contain_text("leave forward")
    expect(compared.locator(".lf-shortcut-bar")).not_to_contain_text("leave backward")
    # The reference reads the same declaration, but it is a modal and global chrome: its
    # entry dismisses the menu the way the platform dismisses any auto popover. The bar
    # speaks for the live scene and names only the direction the user can take; the
    # reference is a catalogue and names both, each marked as reachable in the menu
    # rather than here. Which is the whole of what the pair is for: a user who cannot
    # read the second direction anywhere cannot learn that the row has one.
    compared.keyboard.press("?")
    compared.keyboard.press("?")
    reference = compared.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(compared.locator(".lf-version-menu")).to_be_hidden()
    expect(reference).to_contain_text("Leave the versions menu forward")
    expect(reference).to_contain_text("Leave the versions menu backward")
    assert compared.evaluate(
        """() => Object.fromEntries(
          ['version.leave-forward', 'version.leave-backward'].map(command => [
            command,
            document.querySelector(
              `.lf-command-reference-command[data-lf-command="${command}"]`
            )?.dataset.lfAvailable ?? null,
          ])
        )"""
    ) == {"version.leave-forward": "false", "version.leave-backward": "false"}
    compared.keyboard.press("Escape")
    expect(reference).to_be_hidden()

    open_versions(compared)
    expect(compared.locator(".lf-version-menu")).to_be_visible()

    # Holding Tab sends repeated keydowns after the first stop. The boundary action must
    # repeat too: leaving the browser's focus move native does not mean leaving the menu
    # painted over the control that move reaches.
    compared.locator('.lf-version-row[data-lf-version="2"]').focus()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-diff[data-lf-version="1"]')).to_be_focused()
    compared.keyboard.down("Tab")
    compared.keyboard.up("Tab")
    expect(compared.locator(".lf-version-menu")).to_be_hidden()

    open_versions(compared)
    comparison.focus()
    compared.keyboard.down("Shift")
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    compared.keyboard.down("Tab")
    compared.keyboard.up("Tab")
    compared.keyboard.up("Shift")
    expect(compared.locator(".lf-version-menu")).to_be_hidden()
    compared.close()

    page = open_page(browser, url, pin=True)

    open_versions(page)
    expect(page.locator(".lf-version-menu")).to_be_visible()
    # Both keys on both surfaces, off the one declaration.
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("⏎ / space")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text("⏎ / space")
    expect(page.locator(".lf-command-reference")).to_contain_text("Open that version")
    page.keyboard.press("Escape")

    # And the key the row had been leaving unnamed does what the row now says it does,
    # on the menu stood up again after the reference dismissed it.
    open_versions(page)
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.locator('.lf-version-row[data-lf-version="2"]').focus()
    page.keyboard.press("Space")
    page.wait_for_url(re.compile(r"/versions/v2\.html\?pin=$"))


def test_the_current_page_has_a_menu_local_key(browser, serve):
    """A pinned version stays where the user put it and offers the current page as a chip. The
    keyboard reaches that chip's destination through the picker rather than past it: g V
    opens the menu and its local v takes the live page, by that row's own press, so the key
    leaves through the door the pointer uses and the historical URL stays exact.

    Which is the newest row, not the row the walk stands on — that one is Enter's, and a
    user who has walked away from where they started must still be able to say "the
    current state" in one press. And the second press carries no liveness of its own,
    which is the point of spelling the move this way: the menu always has a current row,
    so the motion holds wherever the user is — including on the page already reading
    that row, where a key of the page's own would have had to stand down and every
    surface say so."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    page = open_page(browser, url, pin=True)
    menu = page.locator(".lf-version-menu")
    help_el = page.locator(".lf-command-reference")
    page.locator(".lf-banner-more").click()
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    page.keyboard.press("Escape")

    # The menu's keys are one declaration, so the reference names this one beside the
    # walk it saves.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Open the current page")
    page.keyboard.press("Escape")

    # The first press opens and goes nowhere. A whole tick passes before the reading,
    # which is far longer than a navigation would take to start.
    pinned = page.url
    open_versions(page)
    expect(menu).to_be_visible()
    ticked(page)
    assert page.url == pinned, "the press that opens the menu navigated"

    # Walk off the version being read, so the row under the focus is not the current one and
    # not the one this press takes.
    page.keyboard.press("ArrowUp")
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    page.keyboard.press("v")
    page.wait_for_url(re.compile(r"/$"))
    # The rebuilt list is what says the page arriving here has heard from the server.
    # A hidden chip does not: that is also how the banner stands before the first poll,
    # so an assertion on it alone would read the same on a page that had heard nothing —
    # and the reference below is written by that same poll.
    expect(page.locator(".lf-version-row")).to_have_count(3)
    expect(page.locator(".lf-latest-chip")).to_be_hidden()

    # And it is still offered here, with the chip gone: opening the current page is
    # what the press does on the page already reading it, so no surface stands it down.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("Open the current page")


def test_a_data_bound_diff_aims_and_selects_one_source_line(browser, serve):
    """The data feed supplies the patch while its line key supplies both comment routes.

    Both sides use the same source line number, so Alt-click proves the whole-line route
    preserves its side. The precise selection ends at offset zero in the next syntax token:
    exactly the boundary where sentence snapping once absorbed the interpolation's closing
    brace and quote. Both comments must store the new side's datum, while only the selection
    adds the exact expression as a quote.
    """
    authored = leaf_page(
        "data-bound diff",
        '<h1 id="title">Review</h1><div style="height: 900px"></div>'
        '<lf-diff id="patch" source="review-patch">'
        "<pre></pre></lf-diff>",
    )
    url = serve(authored)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def route(request):
-    return f"legacy:{request.token.id}"
+    return f"tok:{request.token.id}"
""",
    )
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    old_key = '["app.py","old",2]'
    new_key = '["app.py","new",2]'
    deleted = page.locator(
        f"lf-diff [data-line-type=\"change-deletion\"][data-lf-datum='{old_key}']"
    )
    added = page.locator(
        f"lf-diff [data-line-type=\"change-addition\"][data-lf-datum='{new_key}']"
    )
    expect(deleted).to_have_count(1)
    expect(added).to_have_count(1)
    expect(deleted).to_have_attribute("data-lf-datum-label", "app.py · old line 2")
    assert added.get_attribute("data-lf-projection") == "patch"
    expect(added).to_have_attribute("data-lf-datum-label", "app.py · new line 2")
    expect(added).to_have_attribute("aria-description", "app.py · new line 2")
    expect(added).to_have_attribute("data-lf-source", "review-patch")
    revision = source_revision(serve.page_dir, "review-patch")
    expect(added).to_have_attribute("data-lf-source-revision", revision)

    details = page.locator("lf-diff details").first
    summary = details.locator("summary")
    file_row = page.locator("lf-diff .lf-diff-file").first
    expect(file_row).to_have_attribute("data-lf-datum", '["app.py","file"]')
    expect(file_row).to_have_attribute("data-lf-datum-label", "app.py · file")
    details.evaluate(
        "element => { element.open = false; window.__lfDiffDetails = element; }"
    )
    page.evaluate(
        """async () => {
          const {notifyDataSubscribers} = await window.__lfRuntimeImport('/runtime/data.js');
          await notifyDataSubscribers();
        }"""
    )
    assert details.evaluate("element => element === window.__lfDiffDetails")
    expect(details).not_to_have_attribute("open", "")
    details.evaluate("element => { element.open = true; }")

    summary.hover(position={"x": 100, "y": 10})
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_be_visible()
    page.keyboard.up("Alt")
    summary.click(modifiers=["Alt"])
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_contain_text("§ app.py · file")
    expect(details).to_have_attribute("open", "")
    page.keyboard.press("Escape")

    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    datum_hint = added.evaluate(
        """line => {
          const box = line.getBoundingClientRect();
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((left, right) => {
              const a = left.getBoundingClientRect(), b = right.getBoundingClientRect();
              return Math.hypot(a.left - box.left, a.top - box.top)
                   - Math.hypot(b.left - box.left, b.top - box.top);
            })[0].dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(datum_hint)
    expect(page.locator(".lf-live")).to_contain_text("Chosen app.py · new line 2")
    page.keyboard.press("Escape")

    line_comment = page.get_by_role(
        "button", name="Comment on app.py · new line 2", exact=True
    )
    added.hover()
    expect(line_comment).to_be_visible()
    line_comment.click()
    composer_outlet = page.locator(
        f"lf-diff .lf-diff-thread-outlet[data-lf-thread-datum='{new_key}']"
    )
    expect(composer_outlet.locator(".lf-fab-bar")).to_be_visible()
    input_ = composer_outlet.locator(".lf-fab-input")
    expect(input_).to_be_focused()
    page.emulate_media(media="print")
    expect(composer_outlet.locator(".lf-fab-bar")).to_be_hidden()
    page.emulate_media(media="screen")
    expect(composer_outlet.locator(".lf-fab-bar")).to_be_visible()
    input_.focus()
    write(input_, "Review the whole added line.")
    input_.evaluate("input => input.setSelectionRange(7, 16)")
    page.evaluate(
        """async () => {
          const {threadSurface} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          threadSurface(document.querySelector('#patch')).update();
        }"""
    )
    expect(input_).to_be_focused()
    assert input_.evaluate("input => [input.selectionStart, input.selectionEnd]") == [
        7,
        16,
    ]
    # Folding the file away removes the inline outlet, but the draft remains on
    # screen with its words and focus until the file is opened again.
    details.evaluate("element => { element.open = false; }")
    expect(composer_outlet).to_have_count(0)
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "Review the whole added line."
    )
    details.evaluate("element => { element.open = true; }")
    expect(composer_outlet.locator(".lf-fab-input")).to_have_js_property(
        "value", "Review the whole added line."
    )
    expect(composer_outlet.locator(".lf-fab-input")).to_be_focused()
    with sending(page, "the comment returned to from the draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    inline = page.locator("lf-diff .lf-diff-thread-outlet")
    expect(inline).to_have_count(1)
    expect(inline.locator(".lf-page-thread")).to_contain_text(
        "Review the whole added line."
    )
    alignment = inline.evaluate(
        """outlet => {
          const root = outlet.getRootNode();
          const gutter = root.querySelector('.lf-diff-thread-gutter');
          const contentBox = outlet.getBoundingClientRect();
          const gutterBox = gutter.getBoundingClientRect();
          return {
            top: Math.abs(contentBox.top - gutterBox.top),
            bottom: Math.abs(contentBox.bottom - gutterBox.bottom),
            contentRows: getComputedStyle(outlet.parentElement).gridRow,
            gutterRows: getComputedStyle(gutter.parentElement).gridRow,
          };
        }"""
    )
    assert alignment["top"] < 0.5 and alignment["bottom"] < 0.5, alignment
    assert alignment["contentRows"] == alignment["gutterRows"], alignment
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    details.evaluate("element => { element.open = false; }")
    expect(inline).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(1)
    details.evaluate("element => { element.open = true; }")
    expect(inline).to_have_count(1)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    page.locator(".lf-thread-summary").first.click()
    whole_line = page.locator(".lf-threads > .lf-thread .lf-quote").first
    expect(whole_line).to_have_text("§ app.py · new line 2")
    search = page.locator("#patch .lf-diff-search input")
    search.fill("nothing-matches")
    expect(added).to_be_hidden()
    expect(inline).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(1)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    expect(added).not_to_be_in_viewport()
    whole_line.click()
    expect(search).to_have_value("")
    expect(added).to_be_in_viewport()
    expect(added).to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(deleted).not_to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(inline).to_have_count(1)
    expect(inline.locator("leaf-text")).to_be_focused()
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, False)

    selected = added.evaluate(
        """line => {
          const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
          const nodes = [], starts = [];
          let flat = '';
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            starts.push(flat.length); nodes.push(node); flat += node.data;
          }
          const phrase = 'request.token.id';
          const start = flat.indexOf(phrase);
          if (start < 0) return null;
          const at = offset => {
            const index = starts.findLastIndex(value => value <= offset);
            return [nodes[index], offset - starts[index]];
          };
          const pointer = {bubbles: true, composed: true, isPrimary: true,
                           pointerType: 'mouse', button: 0};
          line.dispatchEvent(new PointerEvent('pointerdown', pointer));
          const range = document.createRange();
          range.setStart(...at(start));
          range.setEnd(...at(start + phrase.length));
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          line.dispatchEvent(new PointerEvent('pointerup', pointer));
          line.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, composed: true}));
          return {
            text: selection.toString(),
            crossesTokens: range.startContainer !== range.endContainer,
            endsAtTokenStart: range.endOffset === 0,
          };
        }"""
    )
    assert selected == {
        "text": "request.token.id",
        "crossesTokens": True,
        "endsAtTokenStart": True,
    }, selected
    open_selected_comment(page)
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_contain_text("“request.token.id”")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    write(page.locator(".lf-fab-input"), "Review this expression.")
    with sending(page, "the comment on the selected expression"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-thread .lf-quote").nth(1)).to_have_text(
        "app.py · new line 2 · “request.token.id”"
    )

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [comment["anchor"] for comment in comments] == [
        {
            "section": "patch",
            "datum": new_key,
            "source": "review-patch",
            "source_revision": revision,
        },
        {
            "section": "patch",
            "datum": new_key,
            "source": "review-patch",
            "source_revision": revision,
            "quote": "request.token.id",
        },
    ]

    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def route(request):
-    return f"legacy:{request.token.id}"
+    return f"replacement:{request.token.id}"
""",
    )
    told(page)
    expect(inline).to_have_count(0)
    expect(added).not_to_have_class(re.compile(r"\blf-mark-here\b"))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    expect(page.locator(".lf-thread .lf-anchor-status")).to_have_count(2)
    expect(page.locator(".lf-thread .lf-anchor-status")).to_have_text(
        ["Earlier data", "Earlier data"]
    )
    quote_classes = page.locator(".lf-thread .lf-quote").evaluate_all(
        "quotes => quotes.map(quote => [...quote.classList])"
    )
    assert all("detached" not in classes for classes in quote_classes), quote_classes


def test_a_diff_surface_keeps_the_complete_thread_lifecycle_inline(browser, serve):
    """The diff owns only the row. Core's shared Thread view keeps replies,
    reactions, settlement, and resolved-thread rendering working inside it.

    The inline seat and the panel are two views of one thread: the same workflow
    lines, updated in place, and one draft. How a send from this seat is delivered,
    and how the seat looks, belong to the `inline` case of
    `test_render_thread_snapshots.py`."""
    authored = leaf_page(
        "inline diff thread",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
        "<pre></pre></lf-diff>",
    )
    url = serve(authored)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )
    page = open_page(browser, url)
    resized(page, 1920, 900)
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root["id"]}"]')
    panel_thread = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    expect(thread).to_have_count(1)
    expect(thread).to_have_attribute("open", "")
    expect(thread.locator("leaf-text")).to_be_visible()

    # News updates the root's workflow line in both views, in place.
    inline_status = thread.locator(
        ":scope > .lf-thread-content > .lf-thread-transcript > .lf-msg:first-child > .lf-msg-head .lf-msg-sending"
    )
    panel_status = panel_thread.locator(
        ".lf-thread-transcript > .lf-msg:first-child > .lf-msg-head .lf-msg-sending"
    )
    expect(inline_status).to_have_text("Sent")
    expect(panel_status).to_have_text("Sent")
    inline_status.evaluate("node => { node.dataset.identityProbe = 'inline'; }")
    panel_status.evaluate("node => { node.dataset.identityProbe = 'panel'; }")
    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, [root])
    told(page)
    expect(inline_status).to_have_text("Picked up")
    expect(panel_status).to_have_text("Picked up")
    expect(inline_status).to_have_attribute("data-identity-probe", "inline")
    expect(panel_status).to_have_attribute("data-identity-probe", "panel")
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root["id"],
            "responds": root["id"],
            "text": "The guard now covers the replacement path.",
        },
    )
    told(page)
    expect(inline_status).to_have_count(0)
    expect(panel_status).to_have_count(0)

    # The keyboard reaches the seat directly and through the comment note, without
    # opening Threads.
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.keyboard.press("Escape")
    note = page.locator(".lf-mark-note")
    note.focus()
    note.press("Enter")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    # One draft, across the shadow boundary.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    panel_thread.locator(".lf-thread-summary").click()
    inline_send = thread.locator(".lf-compose-submit")
    panel_send = panel_thread.locator(".lf-compose-submit")
    expect(inline_send).to_be_disabled()
    expect(panel_send).to_be_disabled()
    write(thread.locator("leaf-text"), "One draft in both views.")
    expect(panel_thread.locator("leaf-text")).to_have_js_property(
        "value", "One draft in both views."
    )
    expect(inline_send).to_be_enabled()
    expect(panel_send).to_be_enabled()
    write(panel_thread.locator("leaf-text"), "")
    expect(inline_send).to_be_disabled()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, False)

    expect(thread.locator(f'.lf-msg[data-event="{reply["id"]}"]')).to_be_visible()

    # Each message's workflow line reads the same in both views.
    question = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "revision": 1,
            "text": "Please check the inline placement in both thread views.",
        },
    )
    told(page)
    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(serve.page_dir),
            question["id"],
            "checking the inline placement",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    followup = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "revision": 1,
            "text": "And keep a later comment visibly separate.",
        },
    )
    told(page)
    # The seat holds arrivals that would move the diff on screen behind its notice:
    # the user's own two messages. The agent's reply, already read, is not among them.
    thread.get_by_role("button", name="2 new messages").click()
    line = ":scope > .lf-msg-head .lf-msg-sending"
    for view, message_attr in ((thread, "data-event"), (panel_thread, "data-mid")):
        expect(
            view.locator(f'.lf-msg[{message_attr}="{question["id"]}"]').locator(line)
        ).to_have_text("Working")
        expect(
            view.locator(f'.lf-msg[{message_attr}="{followup["id"]}"]').locator(line)
        ).to_have_text("Sent")

    strip = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-react-strip')
    strip.locator(".lf-react-trigger").click()
    with sending(page, "the inline reaction"):
        strip.locator('.lf-react[data-token="change"]').click()
    reacted = events_model.read_events(serve.page_dir)[-1]
    assert (reacted["kind"], reacted["parent"], reacted["token"]) == (
        "reply",
        reply["id"],
        "change",
    )

    # Resolve is the thread's own control, reached by the keyboard like any other.
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    resolve.focus()
    with sending(page, "the inline keyboard resolution"):
        page.keyboard.press("Enter")
    expect(thread).not_to_have_attribute("open", "")
    summary = thread.locator(".lf-page-thread-summary")
    expect(summary).to_have_text("Resolved · 4 messages")
    expect(thread.locator(".lf-msg").first).to_be_hidden()
    summary.click()
    expect(thread.locator(".lf-msg").first).to_be_visible()
    with sending(page, "the inline reopening"):
        thread.get_by_role("button", name="Reopen", exact=True).click()
    expect(thread).to_have_attribute("open", "")
    expect(summary).to_be_hidden()
    expect(thread.locator("leaf-text")).to_be_visible()
