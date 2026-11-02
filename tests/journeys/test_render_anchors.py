"""Selection, passage, syntax, and version-travel tests."""

import re
from html import escape

import pytest
from browser.test_render_anchors import (
    DIFF_EMPTY_CONTEXT_MARKUP,
    DIFF_INERT_SOURCE,
    DIFF_MIXED_RENAME_SOURCE,
    DIFF_PATCH_CASES,
)
from click.testing import CliRunner
from interact_support import append_carried_log_record, record_claim, wait_for
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_navigation import (
    _publish,
    source_revision,
)
from render_harness import (
    INLINE_PAGE,
    PANEL_THREAD,
    PASSAGE_SOURCES,
    RELEASE_FOCUS,
    command_reference_rows,
    compare_with,
    consume_browser_errors,
    expect_panel_offers,
    expect_panel_says,
    leaf_page,
    open_page,
    panel_field,
    panel_menu,
    panel_settled,
    resized,
    scroll_settled,
    sending,
    told,
    wait_for_revision,
    write,
)

from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import passages as passages_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf.registry.storage import read_page_registry
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.example_data import patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_anchors import open_selected_comment
from browser.threads import open_panel_thread

from journeys import (
    first_thread_quote,
)


@pytest.mark.parametrize("source", PASSAGE_SOURCES, ids=lambda source: source.stem)
def test_real_page_passages_can_be_quoted(browser, serve, source):
    """Passages in four unlike authored pages are quotable.

    A passage's shape is what has made selection and search come apart: its block,
    the widgets around it, whether the runtime says it, and the text transform and
    white space it is set in. The sweep drags once across each pair of shapes that
    stand next to each other, which crosses both shapes' own words as well as their
    join, and across a shape alone only where no pair holding it resolved as one
    passage; a repeat of a drag it has already made adds time and no evidence.

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
        const {pageRange} = await window.__lfCheckApi();
        const {TEXT_BLOCK} = await window.__lfCheckApi();
        const {anchorForRange, resolveAnchor} =
            await window.__lfCheckApi();
        const {nextRender} = await window.__lfWidgetApi();
        const {renderingState} = await window.__lfCheckApi();
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
        const commentField = () => document.querySelector('.lf-fab-input');
        const commentOffered = () => commentField()?.checkVisibility({visibilityProperty: true});
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
        // Each block reaching into the next — a drag rarely stops tidily on a
        // boundary, and spanning two blocks is where the joins show. A pair crosses
        // both blocks' own words too, so a shape some pair resolved exactly needs no
        // drag of its own. A shape whose every pair crosses a fence (a tab, an option,
        // generated words) resolves no pair exactly, so it gets one drag across
        // itself alone: otherwise nothing would check its mark.
        const pairs = new Map();
        blocks.forEach((block, i) => {
            const next = blocks[i + 1];
            if (!next) return;
            const join = `${shape(block)} | ${shape(next)}`;
            if (!pairs.has(join)) pairs.set(join, [block, next]);
        });
        const missed = [], skipped = [], astray = [], nonexact = [];
        let attempted = 0, detached = 0, fallback = 0;
        // Whether the drag's mark was checked: true once it resolved as one passage.
        const drag = async (start, end) => {
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
            // Counted, not shrugged off: a selection the field declines to offer is
            // a passage silently outside this sweep, and the sweep is the coverage.
            if (!commentOffered()) {
                skipped.push(range.toString().replace(/\\s+/g, ' ').trim().slice(0, 70));
                return false;
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
                if (range.collapsed || !range.toString().trim())
                    missed.push('unusable native selection: ' + range.toString().slice(0, 70));
                sel.removeAllRanges();
                await rendered();
                return false;
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
            for (let i = 0; commentOffered() && i < 1000; i++) await tick();
            if (commentOffered())
                missed.push('Comment stayed open once the selection cleared');
            return true;
        };
        const checked = new Set();
        for (const [start, end] of pairs.values())
            if (await drag(start, end)) checked.add(shape(start)).add(shape(end));
        const alone = new Map();
        for (const block of blocks)
            if (!checked.has(shape(block)) && !alone.has(shape(block)))
                alone.set(shape(block), block);
        for (const block of alone.values()) await drag(block, block);
        return {attempted, detached, fallback, missed, skipped, astray, nonexact};
    }"""
    )
    # Refusing a highlight needs evidence independent of browser resolution. A
    # regression that detaches ordinary file-readable prose must fail this sweep.
    passages = passages_model.page_passages(
        structure_model.SourceDocument((serve.page_dir / "index.html").read_text()),
        read_page_registry(serve.page_dir).registry,
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
        f"{len(result['skipped'])} passages in {source.stem} raised no Comment field, "
        f"so this sweep never tested them: {result['skipped']}"
    )
    assert result["astray"] == [], (
        f"{len(result['astray'])} passages in {source.stem} painted outside what was "
        f"selected: {result['astray']}"
    )


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
            + '<lf-draft id="draft"><pre>A draft copies its own Markdown.</pre></lf-draft>',
            head="<style>#plain { anchor-name: --authored-plain; }"
            "#numbered.lf-rendered > pre { anchor-name: --authored-numbered; }</style>",
        )

    url = live_url(serve(document()))
    page = open_page(browser, url)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    # The draft's control is its own (`lf-draft.js`); these are the code blocks'.
    expect(page.locator("#draft .lf-draft-tools > .lf-code-copy")).to_have_count(1)
    controls = page.locator(".lf-code-copy:not(#draft *)")
    expect(controls).to_have_count(3)
    document_controls = page.locator(".lf-chrome .lf-code-copy")
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
                    copy: rect(copy.getBoundingClientRect()),
                  };
                }""",
                pre_selector,
            )

        before = geometry()
        assert before["padding"] == "12px", before
        # Copy's toolbar stands just inside the block's top-right corner.
        frame, overlay = before["frame"], before["copy"]
        assert 0 <= overlay[1] - frame[1] <= 8, before
        assert 0 <= frame[0] + frame[2] - overlay[0] - overlay[2] <= 8, before
        if keyboard:
            # Enter on the source copies it, though the control stands outside
            # authored markup and the Tab sequence. The register names that press
            # wherever it names keys: the command reference and the block's
            # aria-keyshortcuts.
            pre.focus()
            expect(pre).to_have_attribute("aria-keyshortcuts", "Enter")
            page.keyboard.press("?")
            expect(
                command_reference_rows(page, "On a code block").get_by_text(
                    "Copy code", exact=True
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
        for box in ("frame", "source", "copy"):
            assert after[box] == pytest.approx(before[box], abs=0.5), (before, after)
        if keyboard:
            page.keyboard.press("Enter")
            expect(pre).to_be_focused()
        else:
            button.click()
        expect(button).to_have_attribute("aria-label", "Code copied")
        expect_panel_says(page, "Code copied")
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
    # A finger shows no intent before it lands, so the corner control stays hidden, and
    # out of a press's way, until a tap stands the user on the block: the touch form of
    # hover.
    touch_control = touch.locator(".lf-chrome .lf-code-copy")
    touch_button = touch_control.get_by_role("button")
    expect(touch_control).to_have_count(1)
    expect(touch_control).to_have_css("opacity", "0")
    expect(touch_control).to_have_css("pointer-events", "none")
    expect(touch.locator("#plain")).to_have_css("padding-top", "12px")

    def copied(expected):
        wait_for(
            lambda: touch.evaluate("navigator.clipboard.readText()"),
            lambda text: text == expected,
            failure="the clipboard never held the copied text",
        )

    touch_pre = touch.locator("#plain")
    frame = touch_pre.bounding_box()
    # The tap that reveals the control does not also press it, though its click is
    # aimed once the control shows.
    touch.evaluate("navigator.clipboard.writeText('cleared')")
    corner = touch_control.bounding_box()
    touch.touchscreen.tap(
        corner["x"] + corner["width"] / 2, corner["y"] + corner["height"] / 2
    )
    expect(touch_control).to_have_css("opacity", "1")
    rendered(touch)
    expect(touch_button).to_have_accessible_name("Copy code")
    assert touch.evaluate("navigator.clipboard.readText()") == "cleared"
    touch.locator("#title").tap()
    expect(touch_control).to_have_css("opacity", "0")

    touch_pre.tap(position={"x": 20, "y": 20})
    expect(touch_pre).to_be_focused()
    expect(touch_pre).to_have_attribute("tabindex", "0")
    expect(touch_control).to_have_css("opacity", "1")
    # The face follows the block's line, and its reach meets a finger's floor: a tap
    # inside that floor but beside the face still presses Copy.
    face = touch_button.bounding_box()
    floor = touch.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--aim-floor'))"
    )
    assert face
    touch.touchscreen.tap(
        face["x"] + face["width"] / 2, face["y"] + face["height"] / 2 + floor / 2 - 2
    )
    expect_panel_says(touch, "Code copied")
    copied(plain)
    assert touch_pre.bounding_box() == frame
    touch.locator("#title").tap()
    expect(touch_control).to_have_css("opacity", "0")

    # The source owns a finger's horizontal swipe. Focus must not cancel the native
    # scroll.
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

    def suffix_uncovered():
        reading = touch_pre.evaluate(
            """(pre, suffix) => {
          const text = pre.querySelector('code').firstChild;
          const range = new Range();
          range.setStart(text, text.length - suffix.length);
          range.setEnd(text, text.length);
          const rect = range.getBoundingClientRect();
          const copy = document.querySelector('.lf-chrome .lf-code-copy');
          const hit = document.elementFromPoint(rect.right - 2, rect.top + rect.height / 2);
          return {covered: hit === copy || copy.contains(hit),
                  suffix: range.toString(),
                  start: [rect.left, rect.top + rect.height / 2],
                  end: [rect.right, rect.top + rect.height / 2],
                  frame: [pre.getBoundingClientRect().left, pre.getBoundingClientRect().right]};
        }""",
            suffix,
        )
        assert not reading["covered"], reading
        assert reading["suffix"] == suffix
        assert reading["frame"][0] < reading["start"][0]
        assert reading["end"][0] < reading["frame"][1]

    # Leaving the block hides the control, and the words beneath it take presses again.
    touch.locator("#title").tap()
    suffix_uncovered()
    touch.locator("#title").tap()
    expect(touch_pre).to_have_attribute("tabindex", "0")

    # A fitting dense line ends where the corner control would stand: its final
    # characters are readable and take presses on arrival, before any tap.
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
    frame = touch_pre.bounding_box()
    suffix_uncovered()
    touch_pre.tap(position={"x": 20, "y": 20})
    expect(touch_pre).to_be_focused()
    # The control takes no press while it still says its last copy succeeded.
    touch.wait_for_function(
        "() => !document.querySelector('.lf-chrome .lf-code-copy').isCopying"
    )
    touch.keyboard.press("Enter")
    copied(fitting)
    expect(touch_pre).to_be_focused()
    expect(touch_pre).to_have_attribute("tabindex", "0")
    assert touch_pre.bounding_box() == frame

    # The widget's source keeps a tab stop for its reading commands even when wrapping
    # removes overflow. Touch focus reveals the same corner copy control.
    numbered_pre = touch.locator("#numbered > pre")
    numbered_control = touch.locator("#numbered > .lf-code-copy")
    expect(numbered_pre).to_have_attribute("tabindex", "0")
    expect(numbered_control).to_have_css("opacity", "0")
    numbered_pre.tap(position={"x": 20, "y": 20})
    expect(numbered_pre).to_be_focused()
    expect(numbered_control).to_have_css("opacity", "1")
    touch.evaluate("navigator.clipboard.writeText('cleared')")
    numbered_control.get_by_role("button").tap()
    copied(widget)
    touch.locator("#title").tap()
    expect(numbered_pre).to_have_attribute("tabindex", "0")
    expect(numbered_control).to_have_css("opacity", "0")


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

    # Versions lists them newest first.
    versions = panel_menu(page, "versions")
    rows = versions.locator(".lf-fp-version > .lf-fp-item")
    expect(rows).to_have_count(10)
    assert [next(re.finditer(r"^v\d+", t)).group() for t in rows.all_inner_texts()] == [
        f"v{n}" for n in range(10, 0, -1)
    ]
    # The bases a diff can run against are every version older than this one, so the
    # first Compare in the list is v9 — which is what "the version before this" comes
    # to once the ordering has decided it.
    presses = versions.locator(".lf-fp-compare")
    expect(presses).to_have_count(9)
    expect(presses.first).to_have_attribute("aria-label", "Compare with v9")
    page.locator(".lf-fp-leaf").click()
    compare_with(page)
    expect(page.locator(".lf-fp-row")).to_contain_text("since v9")
    # Nothing is newer than v10, so nothing offers one.
    expect_panel_offers(page, "latest", offered=False)
    page.close()

    # Pinned to the oldest, the row naming the newest is the runtime's one place that
    # spells a version out in a sentence.
    page = open_page(browser, url, pin=True)
    expect(panel_menu(page).locator('.lf-fp-item[data-row="latest"]')).to_have_text(
        "New page available → open v10"
    )


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
        "</lf-diff>",
    )
    url = serve(authored)
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def route(request):
-    return f"legacy:{request.token.id}"
+    return f"tok:{request.token.id}"
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-Routes by legacy key.
+Routes by token.
"""
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
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
    expect(summary).to_have_attribute("data-lf-datum", '["app.py","file"]')
    expect(summary).to_have_attribute("data-lf-datum-label", "app.py · file")
    details.evaluate(
        "element => { element.open = false; window.__lfDiffDetails = element; }"
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    told(page)
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
          const {threadSurface} = await window.__lfWidgetApi();
          threadSurface(document.querySelector('#patch')).update();
        }"""
    )
    expect(input_).to_be_focused()
    assert input_.evaluate("input => [input.selectionStart, input.selectionEnd]") == [
        7,
        16,
    ]
    # Folding the file away removes the inline outlet and withholds its seated
    # editor. The native draft and its words return when the file opens again.
    details.evaluate("element => { element.open = false; }")
    expect(composer_outlet).to_have_count(0)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "Review the whole added line."
    )
    details.evaluate("element => { element.open = true; }")
    expect(composer_outlet.locator(".lf-fab-bar")).to_be_visible()
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
          const reader = outlet.closest('code[data-code]').getBoundingClientRect();
          const box = outlet.getBoundingClientRect();
          return {left: Math.abs(box.left - reader.left),
                  width: Math.abs(box.width - reader.width)};
        }"""
    )
    assert alignment["left"] < 0.5 and alignment["width"] < 0.5, alignment
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    details.evaluate("element => { element.open = false; }")
    expect(inline).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(1)
    details.evaluate("element => { element.open = true; }")
    expect(inline).to_have_count(1)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    whole_line = first_thread_quote(page, serve.page_dir)
    expect(whole_line).to_have_text("§ app.py · new line 2")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    search = page.locator("#patch .lf-diff-search input")
    search.fill("nothing-matches")
    expect(added).to_be_hidden()
    expect(inline).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(1)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    expect(added).not_to_be_in_viewport()
    # The thread's view goes to the line it quotes with Show on page.
    first_thread_quote(page, serve.page_dir)
    page.locator(".lf-fp-head").get_by_role("button", name="Show on page").click()
    expect(search).to_have_value("")
    expect(added).to_be_in_viewport()
    expect(added).to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(deleted).not_to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(inline).to_have_count(1)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    panel_settled(page, open=False)
    # It lands in the thread's reply there, as the field it left was; Escape steps out
    # onto the thread, so the line can be selected.
    expect(inline.locator(".lf-thread-reply leaf-text")).to_be_focused()
    page.keyboard.press("Escape")

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
    second = open_panel_thread(page, comments[1]["id"])
    expect(second.locator(".lf-fp-quote")).to_have_text(
        "app.py · new line 2 · “request.token.id”"
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

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
    for comment in comments:
        view = open_panel_thread(page, comment["id"])
        expect(view.locator(".lf-anchor-status")).to_have_text("Earlier data")
        assert "detached" not in view.locator(".lf-fp-quote").get_attribute("class")


def test_a_diff_surface_keeps_the_complete_thread_lifecycle_inline(browser, serve):
    """The diff owns only the row. Core's shared Thread view keeps replies,
    reactions, settlement, and resolved-thread rendering working inside it.

    The inline seat and the panel's view of the thread are two views of one thread:
    the same workflow lines, updated in place, and one draft. How a send from this seat is delivered,
    and how the seat looks, belong to the `inline` case of
    `test_render_thread_snapshots.py`."""
    authored = leaf_page(
        "inline diff thread",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
        "</lf-diff>",
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
    panel_thread = page.locator(f'{PANEL_THREAD}[data-thread="{root["id"]}"]')
    expect(thread).to_have_count(1)
    expect(thread.locator("leaf-text")).to_be_visible()
    open_panel_thread(page, root["id"])

    # News updates the root's workflow line in both views, in place.
    inline_status = thread.locator(
        ":scope > .lf-thread-content > .lf-thread-transcript > .lf-msg:first-child > .lf-msg-head .lf-msg-sending"
    )
    panel_status = panel_thread.locator(".lf-msg").first.locator(
        ":scope > .lf-msg-head .lf-msg-sending"
    )
    expect(inline_status).to_have_text(re.compile(r"^Queued for "))
    expect(panel_status).to_have_text(re.compile(r"^Queued for "))
    inline_status.evaluate("node => { node.dataset.identityProbe = 'inline'; }")
    panel_status.evaluate("node => { node.dataset.identityProbe = 'panel'; }")
    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, [root])
    told(page)
    expect(inline_status).to_have_text("Delivered")
    expect(panel_status).to_have_text("Delivered")
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
    # opening the thread in the panel.
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    page.keyboard.press("Escape")
    note = page.locator(".lf-mark-note")
    note.focus()
    note.press("Enter")
    expect(thread).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)

    # One draft, across the shadow boundary: the seat's reply and the panel's field.
    open_panel_thread(page, root["id"])
    inline_send = thread.locator(".lf-compose-submit")
    panel_send = page.locator(".lf-fp-field .lf-compose-submit")
    expect(inline_send).to_be_disabled()
    expect(panel_send).to_have_attribute("aria-disabled", "true")
    write(thread.locator("leaf-text"), "One draft in both views.")
    expect(panel_field(page)).to_have_js_property("value", "One draft in both views.")
    expect(inline_send).to_be_enabled()
    expect(panel_send).to_have_attribute("aria-disabled", "false")
    write(panel_field(page), "")
    expect(inline_send).to_be_disabled()
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

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
            "--text",
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
    for view in (thread, panel_thread):
        if view == panel_thread:
            open_panel_thread(page, root["id"])
        expect(
            view.locator(f'.lf-msg[data-event="{question["id"]}"]').locator(line)
        ).to_have_text("On it")
        expect(
            view.locator(f'.lf-msg[data-event="{followup["id"]}"]').locator(line)
        ).to_have_text(re.compile(r"^Queued for "))
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    strip = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-react-strip')
    thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-react-trigger').click()
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
    resolved = page.locator("lf-diff .lf-resolved-threads")
    summary = resolved.locator(":scope > summary")
    expect(summary).to_have_text("Resolved · 1")
    expect(summary).to_be_focused()
    expect(thread.locator(".lf-msg").first).to_be_hidden()
    summary.click()
    expect(thread.locator(".lf-msg").first).to_be_visible()
    with sending(page, "the inline reopening"):
        thread.get_by_role("button", name="Reopen", exact=True).click()
    expect(resolved).to_have_count(0)
    expect(thread.locator("leaf-text")).to_be_visible()


def test_the_widget_reads_the_diff_patch_table(browser, serve):
    """`diff_patch_cases.json` states what lf-diff can present, which it alone
    judges. The widget draws each accepted patch, under the row's paths, as inline
    text and as the manifest `patch_manifest.py` builds from it (whose paths
    `test_interact_document.py` checks), and refuses each row with a `widget` message
    without hiding evidence: inline, quoting the patch it could not draw, and in a
    stored manifest, in the file it cannot draw. Every refusal reaches the author.
    The same page draws the samples above, which the table's rows do not reach."""
    accepted = [case for case in DIFF_PATCH_CASES if "files" in case]
    refused = [case for case in DIFF_PATCH_CASES if "widget" in case]
    # The manifest stores what it is given, so the widget alone refuses a stored
    # file's patch, in that file. The producer groups repeated paths for the widget
    # to judge; the contract itself refuses an empty manifest at `data set`.
    stored = [case for case in refused if case["id"] != "empty"]
    markup = "".join(
        [
            *(
                f'<lf-diff id="text-{case["id"]}"><pre>{escape(case["patch"])}</pre></lf-diff>'
                for case in [*accepted, *refused]
            ),
            *(
                f'<lf-diff id="files-{case["id"]}" source="files-{case["id"]}"></lf-diff>'
                for case in [*accepted, *stored]
            ),
            f'<lf-diff id="inert-diff"><pre>{escape(DIFF_INERT_SOURCE)}</pre></lf-diff>',
            (
                '<lf-diff id="mixed-rename-diff">'
                f"<pre>{escape(DIFF_MIXED_RENAME_SOURCE)}</pre></lf-diff>"
            ),
            (
                '<lf-diff id="final-empty-context-diff">'
                f"<pre>{DIFF_EMPTY_CONTEXT_MARKUP}</pre></lf-diff>"
            ),
        ]
    )
    url = serve(leaf_page("diff patch table", f'<h1 id="cases">Cases</h1>{markup}'))
    for case in [*accepted, *stored]:
        data_model.cmd_data_set(
            serve.page_dir, f"files-{case['id']}", patch_manifest(case["patch"])
        )
    page = open_page(browser, url)
    rendered(page)
    readings = page.locator("lf-diff").evaluate_all(
        """hosts => Object.fromEntries(hosts.map(host => [host.id, {
          rendered: host.classList.contains('lf-rendered'),
          errors: [...new Set([...host.querySelectorAll('.lf-error'),
            ...(host.shadowRoot?.querySelectorAll('.lf-error') ?? [])]
            .map(box => box.firstChild?.textContent ?? null))],
          source: host.querySelector('.lf-error pre')?.textContent ?? null,
          files: [...(host.shadowRoot?.querySelectorAll('.lf-diff-path') ?? [])].map(
            path => (path.querySelector('.lf-diff-destination-path') ?? path)
              .textContent.replaceAll('\\u200b', '')),
        }]))"""
    )
    for case in accepted:
        for form in ("text", "files"):
            reading = readings[f"{form}-{case['id']}"]
            assert reading["rendered"] and not reading["errors"], (case["id"], reading)
            assert reading["files"] == case["files"], (case["id"], reading)
    for case in refused:
        assert readings[f"text-{case['id']}"] == {
            "files": [],
            "rendered": False,
            "errors": [f"<lf-diff> failed: {case['widget']}"],
            "source": case["patch"] or None,
        }, case["id"]
    for case in stored:
        reading = readings[f"files-{case['id']}"]
        assert reading["rendered"], (case["id"], reading)
        assert reading["errors"] == [
            f"That file's diff cannot be shown: {case['widget']}"
        ], (case["id"], reading)
    # Each refusal reaches the author too, naming the diff that could not draw.
    reported = consume_browser_errors(
        page,
        *(f'<lf-diff id="text-{case["id"]}"> failed: ' for case in refused),
        *(f'<lf-diff id="files-{case["id"]}"> failed: ' for case in stored),
    )
    assert len(reported) == len(refused) + len(stored), reported

    result = page.evaluate("""() => {
      const host = document.querySelector('#inert-diff');
      const added = [...host.shadowRoot.querySelectorAll('[data-line]')]
        .find(line => line.dataset.lineType === 'change-addition');
      return {
        text: added.textContent,
        images: host.shadowRoot.querySelectorAll('img').length,
        handlers: host.shadowRoot.querySelectorAll('[onerror]').length,
        executed: globalThis.__lfDiffPwned === 1,
      };
    }""")
    assert result == {
        "text": "<img src=x onerror=globalThis.__lfDiffPwned=1>",
        "images": 0,
        "handlers": 0,
        "executed": False,
    }

    result = page.evaluate("""async () => {
      const host = document.querySelector('#mixed-rename-diff');
      const shadow = host.shadowRoot;
      const renames = [...(shadow?.querySelectorAll('.lf-diff-metadata') ?? [])];
      const rename = renames[0];
      const quotedRename = renames[1];
      const bomRename = renames[2];
      const { says, wrote } = await window.__lfWidgetApi();
      return {
        rendered: host.classList.contains('lf-rendered'),
        error: host.querySelector('.lf-error')?.firstChild?.textContent ?? null,
        details: shadow?.querySelectorAll('details').length ?? 0,
        diffs: shadow?.querySelectorAll('pre').length ?? 0,
        renameCount: renames.length,
        from: rename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        to: rename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        stat: rename?.querySelector('.lf-diff-stat')?.textContent ?? null,
        generated: rename?.dataset.lfGen === '1',
        saidOverride: rename?.hasAttribute('data-lf-said') ?? null,
        quotedFrom:
          quotedRename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        quotedTo: quotedRename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        bomFrom: bomRename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        bomTo: bomRename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        lines: [...(shadow?.querySelectorAll('[data-line]') ?? [])]
          .map(line => line.textContent),
        saysRename: says(document).includes('old-name.js → new-name.js'),
        wroteRename: wrote(document).includes('old-name.js → new-name.js'),
      };
    }""")
    assert result == {
        "rendered": True,
        "error": None,
        "details": 1,
        "diffs": 1,
        "renameCount": 3,
        "from": "old-name.js",
        "to": "new-name.js",
        "stat": "renamed",
        "generated": True,
        "saidOverride": False,
        "quotedFrom": "old\tname.js",
        "quotedTo": "new\tname.js",
        "bomFrom": "\ufeffold.js",
        "bomTo": "\ufeffnew.js",
        "lines": ["const value = 1;", "const value = 2;"],
        "saysRename": True,
        "wroteRename": False,
    }

    result = page.evaluate("""() => {
      const host = document.querySelector('#final-empty-context-diff');
      return {
        rendered: host.classList.contains('lf-rendered'),
        error: host.querySelector('.lf-error')?.firstChild?.textContent ?? null,
        lines: [...(host.shadowRoot?.querySelectorAll('[data-line]') ?? [])]
          .map(line => line.textContent),
      };
    }""")
    assert result == {
        "rendered": True,
        "error": None,
        "lines": ["visible", ""],
    }
