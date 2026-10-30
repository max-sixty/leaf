"""Diffs: comments, filtering and refreshes that keep the reader's inspection, file rows
and their paths, the pinned file header, hunk landing, and print."""

import json

import pytest
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_cases_widgets import (
    DIFF_CLIPPING,
    DIFF_LANDING,
    DIFF_PRESS,
    DIFF_ROW_FILL,
    DIFF_ROW_PLACEMENT,
    LONG_LINE_DIFF_PAGE,
    MANIFEST_DIFF_PAGE,
    MULTI_HUNK_PATCH,
    PANE_DIFF_PAGE,
)
from render_harness import (
    RELEASE_FOCUS,
    consume_browser_errors,
    displayed,
    holding,
    leaf_page,
    open_page,
    resized,
    said,
    scroll_settled,
    select,
    selection_field,
    sending,
    told,
    write,
)

from browser.threads import append_agent_reply
from browser.widgets import (
    _bound_diff,
    expect_walk_says,
)
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.example_data import patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed


LONG_DIFF_PATH = "src/deeply/nested/module/file.rs"


LONG_DIFF_PATCH = (
    f"diff --git a/{LONG_DIFF_PATH} b/{LONG_DIFF_PATH}\n"
    f"--- a/{LONG_DIFF_PATH}\n+++ b/{LONG_DIFF_PATH}\n"
    "@@ -1 +1,81 @@\n fn main() {\n"
    + "".join(f"+    let value_{i} = {i};\n" for i in range(80))
)


def long_diff(id):
    return f'<lf-diff id="{id}"><pre>{LONG_DIFF_PATCH}</pre></lf-diff>'


def test_a_rewrite_reads_its_deletions_above_its_additions(browser, serve):
    """A change of 4 lines into 19 reads as git wrote it, its old lines above its new.
    Pierre re-splits such a change to pair similar lines, which in Leaf's unified
    view set the old function between the new one's 11th and 12th lines."""
    old = [
        "def upload(client, job, payload):",
        '    response = client.post("/objects", json=payload, timeout=10)',
        "    response.raise_for_status()",
        '    return response.json()["object_id"]',
    ]
    new = [
        '"""Upload one artifact."""',
        "",
        "import time",
        "",
        "",
        "def upload(client, job, payload, max_attempts=2):",
        '    key = f"upload:{job.tenant_id}:{job.id}"',
        "    for attempt in range(max_attempts):",
        "        try:",
        "            response = client.post(",
        '                "/objects", json=payload,',
        '                headers={"Idempotency-Key": key}, timeout=10,',
        "            )",
        "            response.raise_for_status()",
        '            return response.json()["object_id"]',
        "        except TimeoutError:",
        "            if attempt + 1 == max_attempts:",
        "                raise",
        "            time.sleep(0.5 * 2**attempt)",
    ]
    path = "src/uploader.py"
    patch = (
        (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{len(old)} +1,{len(new)} @@\n"
            + "".join(f"-{line}\n" for line in old)
            + "".join(f"+{line}\n" for line in new)
        )
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    page = open_page(
        browser,
        serve(
            leaf_page("Rewrite", f'<lf-diff id="rewrite"><pre>{patch}</pre></lf-diff>')
        ),
    )
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    sides = page.evaluate("""() => [
      ...document.querySelector('#rewrite').shadowRoot.querySelectorAll('[data-lf-datum]'),
    ].map(row => JSON.parse(row.dataset.lfDatum)).filter(d => d.length === 3)
      .map(([, side, line]) => `${side}${line}`)""")
    assert sides == [f"old{n}" for n in range(1, 5)] + [
        f"new{n}" for n in range(1, 20)
    ], sides


def _patch_file(path, start, lines):
    """One file's section of a patch whose single hunk, at `start`, adds `lines`."""
    return (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -{start},1 +{start},{len(lines) + 1} @@\n context\n"
        + "".join(f"+{line}\n" for line in lines)
    )


FIRST_PAINT_PAGE = leaf_page(
    "Diff first paint",
    "<h1>Diffs</h1>"
    # Code scrolls: a hunk below the first line draws a separator, and four-digit line
    # numbers widen the gutter.
    + '<lf-diff id="code"><pre>'
    + _patch_file("src/app.py", 1200, ["x = 1", "y = 2"])
    + _patch_file("src/util.py", 1, ["z = 3"])
    + "</pre></lf-diff>"
    # One file draws no filter row.
    + '<lf-diff id="single"><pre>'
    + _patch_file("src/only.py", 1, ["w = 0"])
    + "</pre></lf-diff>"
    # Prose wraps at the drawing's column: words, runs of spaces, and words longer
    # than the column by every count up to a few columns, so a column more or less
    # than the drawing's changes some row's lines at either width.
    + '<lf-diff id="prose"><pre>'
    + _patch_file(
        "docs/guide.md",
        1,
        [
            (
                "A paragraph kept on one source line, long enough to wrap at every "
                "width the page is read at, with words of several lengths to break at."
            ),
            "Spaces    run    between    these    words    before    the    line    "
            * 3,
            "https://example.com/" + "a" * 160,
            *("a" * length for length in range(30, 150)),
        ],
    )
    + _patch_file("notes.txt", 1, ["Plain text wraps too, " * 8])
    + "</pre></lf-diff>"
    + '<lf-diff id="folded" collapsed><pre>'
    + _patch_file("src/app.py", 1, ["x = 1"])
    + _patch_file("src/util.py", 1, ["z = 3"])
    + "</pre></lf-diff>"
    # A selected-file reader opens only its first file, even when authored collapsed.
    # A later metadata-only file contributes no height to that first reading.
    + '<lf-diff id="file-view" view="file" collapsed><pre>'
    + _patch_file("docs/first.md", 1, ["The first file remains readable. " * 12])
    + "diff --git a/later.txt b/later.txt\nold mode 100644\nnew mode 100755\n"
    + '</pre></lf-diff><lf-diff id="relative-font" style="--code-size:1em" overflow="wrap"><pre>'
    + _patch_file(
        "docs/font.md", 1, ["A wrapped row uses its inherited code font. " * 12]
    )
    + "</pre></lf-diff><p id='after'>After the diffs.</p>",
)


@pytest.mark.parametrize(
    "viewport, touch", [((1280, 900), False), ((390, 844), True)], ids=["wide", "touch"]
)
def test_an_inline_patch_stays_readable_until_its_drawing_arrives(
    browser, serve, viewport, touch
):
    """Authored source is readable with modules held; the live drawing then keeps
    file selection, collapsed files, and wrapped prose at desktop and touch widths."""
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        has_touch=touch,
        is_mobile=touch,
    )
    page = context.new_page()
    boot = []
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(FIRST_PAINT_PAGE), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        # First paint can precede later patches; measure their complete authored input.
        page.wait_for_function("document.readyState !== 'loading'")
        sources = page.locator("lf-diff > pre")
        expect(sources).to_have_count(6)
        for source in sources.all():
            expect(source).to_be_visible()
            expect(source).to_contain_text("diff --git")
        boot.pop().continue_()
        wait_until_ready(page)
        page.wait_for_function(
            "() => [...document.querySelectorAll('lf-diff')].every(d => d.matches('.lf-rendered'))"
        )
        expect(page.locator("#code [data-line]").last).to_contain_text("z = 3")
        expect(page.locator("#folded details[open]")).to_have_count(0)
        expect(page.locator("#file-view [data-line]").last).to_contain_text(
            "The first file remains readable."
        )
        expect(page.locator("#file-view .lf-diff-fold:visible")).to_have_count(1)
        expect(page.locator("#relative-font [data-line]").last).to_contain_text(
            "A wrapped row uses its inherited code font."
        )
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_diff_wraps_prose_by_default_and_accepts_an_overflow_choice(browser, serve):
    paragraph = "A changed paragraph should stay within the reader's width. " * 12

    def patch(path):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{paragraph}\n"
        )

    page = open_page(
        browser,
        serve(
            leaf_page(
                "Diff wrapping",
                "".join(
                    f'<lf-diff id="{name}"{attribute}><pre>{patch(path)}</pre></lf-diff>'
                    for name, path, attribute in (
                        ("prose", "README.md", ""),
                        ("plain-text", "notes.txt", ""),
                        ("code", "src/app.py", ""),
                        ("forced-wrap", "src/long.py", ' overflow="wrap"'),
                        ("forced-scroll", "notes.md", ' overflow="scroll"'),
                    )
                ),
            )
        ),
    )
    resized(page, 800, 900)
    page.wait_for_function(
        "() => document.querySelectorAll('lf-diff.lf-rendered').length === 5"
    )
    modes = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('lf-diff')].map(diff => {
        const code = diff.shadowRoot.querySelector('code[data-code]');
        return [diff.id, code.scrollWidth > code.clientWidth + 1];
      })
    )""")
    assert modes == {
        "prose": False,
        "plain-text": False,
        "code": True,
        "forced-wrap": False,
        "forced-scroll": True,
    }, modes
    for medium in ("screen", "print"):
        page.emulate_media(media=medium)
        alignment = page.locator("#prose .lf-diff-line-comment").evaluate_all(
            """buttons => buttons.map(button => {
              const source = button.nextElementSibling;
              const range = document.createRange();
              range.selectNodeContents(button);
              const number = range.getBoundingClientRect();
              range.selectNodeContents(source);
              const text = range.getBoundingClientRect();
              const row = button.parentElement.getBoundingClientRect();
              const marker = getComputedStyle(source, '::before');
              return {top: Math.abs(number.top - text.top),
                gap: row.left + parseFloat(marker.left) - number.right,
                hit: button.getBoundingClientRect().height, height: row.height};
            })"""
        )
        assert max(row["height"] for row in alignment) > 38, alignment
        assert all(
            row["top"] < 1 and row["gap"] >= 2 and row["hit"] == row["height"]
            for row in alignment
        ), (medium, alignment)
    page.emulate_media(media="screen")
    prose_line = page.locator('lf-diff#prose [data-lf-datum=\'["README.md","new",1]\']')
    prose_line.hover()
    page.locator("lf-diff#prose .lf-diff-line-comment").last.click()
    expect(page.locator(".lf-composer")).to_be_visible()


# Scrolls the box with the given id 400px down and reads how far below the top of its
# content and scrollport the diff's file header inside it stands. Ordinary scrollers
# pin below their padding; tab panels put the header at the scrollport's edge.
PINNED_IN_BOX = """async (id) => {
    const box = document.getElementById(id);
    box.scrollTop = 400;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const head = box.querySelector('lf-diff').shadowRoot
        .querySelector('.lf-diff-file > details > summary');
    const edge = box.getBoundingClientRect().top + box.clientTop;
    return {
        scrolled: box.scrollTop,
        gap: head.getBoundingClientRect().top - (edge
            + parseFloat(getComputedStyle(box).paddingTop)),
        scrollportGap: head.getBoundingClientRect().top - edge,
    };
}"""


def test_any_box_that_scrolls_starts_the_sticky_header_slot_again(browser, serve):
    """A diff's file header pins at the top of its declared scroll box, whether a
    page rule, an inline style, `overflow: hidden`, or a column's sticky
    sidebar each start `--lf-top` again, where each pinned the header the root's slot
    below the box's top. The root keeps its slot though a page rule makes it scroll,
    and a page's sticky box keeps the slot it met though another rule makes it scroll,
    so both still stop at the slot's foot. No chrome stands at the window's head, so
    the root's slot is the top safe-area inset, which the page stands in for here as a
    notched phone would give it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Scrolling boxes",
                f'<aside><div class="layout-track" id="side">{long_diff("in-side")}</div></aside>'
                f'<div class="layout-column"><h1>Scrolling boxes</h1><div id="box" class="scroll">{long_diff("in-box")}</div>'
                '<div id="inline" class="scroll" style="max-height: 320px; overflow: auto">'
                f"{long_diff('in-inline')}</div>"
                '<div id="hidden" class="scroll" style="max-height: 320px; overflow: hidden">'
                f"{long_diff('in-hidden')}</div>"
                '<div id="panel" class="tall"><p>Panel.</p></div>'
                + "<p>Filler.</p>" * 60
                + "</div>",
                layout="sidebar",
                head="<style>:root:root { --lf-safe-top: 40px; }"
                "html { overflow-y: scroll; }"
                "#box, .tall { max-height: 320px; overflow: auto; }"
                "#panel { position: sticky; top: var(--lf-top); }</style>",
            )
        ),
    )
    resized(page, 1600, 1000)
    expect(page.locator("#side")).to_have_css("position", "sticky")
    page.wait_for_function(
        "() => document.querySelectorAll('lf-diff.lf-rendered').length === 4"
    )
    read = page.evaluate(
        f"""async () => {{
        const pinned = {PINNED_IN_BOX};
        return {{
            box: await pinned('box'),
            inline: await pinned('inline'),
            hidden: await pinned('hidden'),
            side: await pinned('side'),
            panel: getComputedStyle(document.querySelector('#panel')).top,
            root: getComputedStyle(document.documentElement).getPropertyValue('--lf-top'),
        }};
    }}"""
    )
    for box in ("box", "inline", "hidden", "side"):
        assert read[box]["scrolled"] == 400, read
        assert read[box]["gap"] == pytest.approx(0, abs=1.5), read
    assert read["root"] == "40px" and read["panel"] == read["root"], read


def test_a_diff_pins_to_its_page_tab_panel_or_past_an_option_card(browser, serve):
    """A page tab panel the page makes scroll pins its diff's header to the scrollport
    edge, leaving no padding band where scrolled rows can show above the header.
    An undecided option card clips its rounded corners and scrolls
    nothing, so a diff in an option pins at the root's slot as the page scrolls past it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Panel and option",
                '<lf-tabs id="tabs" class="layout-flow"><lf-tab id="tab" label="Diff">'
                f"{long_diff('in-tab')}</lf-tab></lf-tabs>"
                '<lf-ask id="ask"><h2>Which?</h2><lf-options id="opts" choose>'
                f'<lf-option id="opt-a"><strong>A</strong>{long_diff("in-option")}'
                '</lf-option><lf-option id="opt-b"><strong>B</strong></lf-option>'
                "</lf-options></lf-ask>" + "<p>Filler.</p>" * 60,
                head="<style>#tab { max-height: 320px; overflow: auto; }</style>",
            )
        ),
    )
    resized(page, 1280, 900)
    expect(page.locator("lf-tabs")).to_have_css("--lf-views-flow", "page")
    page.wait_for_function(
        "() => document.querySelectorAll('lf-diff.lf-rendered').length === 2"
    )
    read = page.evaluate(
        f"""async () => {{
        const tab = await ({PINNED_IN_BOX})('tab');
        const diff = document.getElementById('in-option');
        const head = diff.shadowRoot.querySelector('.lf-diff-file > details > summary');
        const rows = [...diff.shadowRoot.querySelectorAll('[data-line]')];
        rows[40].scrollIntoView({{block: 'start', behavior: 'instant'}});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return {{
            tab,
            option: head.getBoundingClientRect().top,
            top: parseFloat(getComputedStyle(document.documentElement)
                .getPropertyValue('--lf-top')),
        }};
    }}"""
    )
    assert read["tab"]["scrolled"] == 400, read
    assert read["tab"]["scrollportGap"] == pytest.approx(0, abs=1.5), read
    assert read["option"] == pytest.approx(read["top"], abs=1), read


def test_inline_diff_lines_and_files_can_start_comments(browser, serve):
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Inline review",
                '<h1>Review</h1><lf-diff id="patch"><pre>' + patch + "</pre></lf-diff>",
            )
        ),
    )
    file = page.locator('lf-diff [data-lf-datum=\'["app.py","file"]\']')
    line = page.locator('lf-diff [data-lf-datum=\'["app.py","new",1]\']')
    expect(file.locator(".lf-diff-file-comment")).to_have_count(1)
    expect(line).to_have_count(1)
    expect(page.locator("lf-diff .lf-diff-line-comment")).to_have_count(2)
    file.locator(".lf-diff-file-comment").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "File note")
    with sending(page, "inline file comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    line.hover()
    page.locator("lf-diff .lf-diff-line-comment").last.click()
    expect(page.locator(".lf-composer")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Line note")
    with sending(page, "inline line comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in comments] == [
        {"section": "patch", "datum": '["app.py","file"]'},
        {"section": "patch", "datum": '["app.py","new",1]'},
    ]


def test_filtering_a_diff_keeps_its_field_and_toolbar_controls_fixed(browser, serve):
    """The matching count leaves the filter field in place at every result count, on a
    phone and on a desktop window. A patch of one file has nothing to filter, so it
    draws no filter."""
    url = serve(MANIFEST_DIFF_PAGE)

    def patch(count):
        return "".join(
            f"diff --git a/src/file-{index}.py b/src/file-{index}.py\n"
            f"--- a/src/file-{index}.py\n+++ b/src/file-{index}.py\n"
            "@@ -1 +1 @@\n-old\n+new\n"
            for index in range(count)
        )

    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(patch(12)))
    page = open_page(browser, url)
    diff = page.locator("#patch")
    search = diff.locator(".lf-diff-search input")
    progress = diff.locator(".lf-diff-progress")
    rows = diff.locator(".lf-diff-file:not([hidden])")
    geometry = """host => Object.fromEntries(
      ['.lf-diff-search', '.lf-diff-progress']
        .map(selector => {
          const node = host.shadowRoot.querySelector(selector);
          if (!node) return [selector, null];
          const {x, y, width, height} = node.getBoundingClientRect();
          return [selector, {x, y, width, height}];
        }))"""

    for width in (390, 1280):
        resized(page, width, 844)
        for total in (12, 2):
            data_model.cmd_data_set(
                serve.page_dir, "review-patch", patch_manifest(patch(total))
            )
            told(page)
            expect(rows).to_have_count(total)
            base_label = f"{total} file{'s' if total != 1 else ''}"
            expect(progress).to_have_text(base_label)
            search.scroll_into_view_if_needed()
            rendered(page)
            before = diff.evaluate(geometry)
            for query, matches in (("file-0.py", 1), ("no-such-file", 0), ("", total)):
                search.fill(query)
                expect(rows).to_have_count(matches)
                expected_label = base_label
                if matches != total:
                    expected_label = f"{matches} of {total}"
                expect(progress).to_have_text(expected_label)
                rendered(page)
                after = diff.evaluate(geometry)
                assert after == before, (width, query, before, after)
                expect(search).to_be_focused()

    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(patch(1)))
    told(page)
    expect(rows).to_have_count(1)
    expect(diff.locator(".lf-diff-search")).to_have_count(0)


def test_a_diff_refresh_keeps_the_readers_inspection(browser, serve):
    """A new patch changes evidence, while file disclosure and reading position
    belong to the reader inspecting the same files. The evidence is a manifest, whose
    files the widget loads one at a time."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch_manifest(MULTI_HUNK_PATCH)
    )
    page = open_page(browser, url)
    page.locator("lf-diff summary").last.click()
    search = page.locator("lf-diff .lf-diff-search input")
    search.fill("handlers")
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']')
    row.scroll_into_view_if_needed()
    scroll_settled(page)
    reading = """() => {
      const diff = document.querySelector('lf-diff');
      return {scroll: scrollY,
              files: diff.shownEntries().map(entry => entry.record.path),
              open: diff.fileEntries.map(entry => entry.details.open),
              focus: diff.shadowRoot.activeElement?.className,
              top: diff.lfDataDatum('[\"app/handlers.py\",\"new\",81]').getBoundingClientRect().top};
    }"""
    before = page.evaluate(reading)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest(MULTI_HUNK_PATCH.replace("new route", "new routing")),
    )
    told(page)
    rendered(page)
    after = page.evaluate(reading)
    expect(search).to_have_value("handlers")
    assert after == before, (before, after)


def test_a_changed_diff_file_keeps_its_sideways_reader(browser, serve):
    """Replacing a file's evidence retains its code scrollport and focused line."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.locator("lf-diff summary").first.click()
    page.keyboard.press("Tab")
    page.locator("lf-diff summary").first.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("]")
    page.keyboard.press("]")
    page.keyboard.press("]")
    reading = """() => {
      const diff = document.querySelector('lf-diff');
      const row = diff.lfDataDatum('[\"app/handlers.py\",\"new\",81]');
      return {scroll: scrollY, sideways: row.closest('code').scrollLeft,
              focus: diff.shadowRoot.activeElement?.dataset.lfDatum};
    }"""
    page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']').evaluate(
        "row => { row.closest('code').scrollLeft = 200; }"
    )
    scroll_settled(page)
    before = page.evaluate(reading)
    assert before["sideways"] == 200
    assert before["focus"] is not None
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        MULTI_HUNK_PATCH.replace("new first", "new beginning"),
    )
    told(page)
    rendered(page)
    after = page.evaluate(reading)
    assert after == before, (before, after)


def two_diff_page(serve):
    """LONG_LINE_DIFF_PAGE with a second diff, `#manifest-patch`, reading its evidence
    from `review-manifest`, so the raw patch and the manifest each refresh in turn on one
    page."""
    return serve(
        LONG_LINE_DIFF_PAGE.replace(
            '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>',
            '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>'
            '<lf-diff id="manifest-patch" source="review-manifest"><pre></pre></lf-diff>',
        )
    )


DIFF_FORMS = (
    ("#patch", "review-patch", lambda patch: patch),
    ("#manifest-patch", "review-manifest", patch_manifest),
)


def test_a_diff_refresh_keeps_a_selection_in_unchanged_lines(browser, serve):
    """A change in another hunk does not take the passage the reader selected, in a
    raw patch and in a manifest: a change in place, one that inserts a line, and a hunk
    added before the kept lines, which moves them down the listing while each keeps its
    own numbered control."""
    url = two_diff_page(serve)
    for _, source, value in DIFF_FORMS:
        data_model.cmd_data_set(serve.page_dir, source, value(MULTI_HUNK_PATCH))
    page = open_page(browser, url)
    patch, manifest = DIFF_FORMS
    for (diff, source, value), edit in (
        (patch, "inserted-line"),
        (manifest, "in-place"),
        (patch, "earlier-hunk"),
        (manifest, "earlier-hunk"),
    ):
        diff_refresh_keeps_selection(page, serve, diff, source, value, edit)


def diff_refresh_keeps_selection(page, serve, diff, source, value, edit):
    """Select a word in an unchanged line of `diff`, change another hunk of `source`,
    and find the selection and every row's gutter pairing intact."""
    row = page.locator(f'{diff} [data-lf-datum=\'["app/handlers.py","new",41]\']')
    row.scroll_into_view_if_needed()
    ends = row.evaluate("""row => {
      const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const start = node.textContent.indexOf('second');
        if (start < 0) continue;
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + 'second'.length);
        const box = range.getBoundingClientRect();
        return [[box.left, box.top + box.height / 2], [box.right, box.top + box.height / 2]];
      }
    }""")
    select(page, *ends)
    before = page.evaluate("() => getSelection().toString()")
    assert before == "second"
    patch = MULTI_HUNK_PATCH.replace("new first", "new beginning")
    if edit == "earlier-hunk":
        patch = patch.replace(
            "@@ -40,5",
            '@@ -20,2 +20,2 @@\n def line_20():\n-    return "old"\n+    return "new"\n'
            "@@ -40,5",
        )
    if edit == "inserted-line":
        patch = patch.replace("@@ -1,5 +1,5 @@", "@@ -1,5 +1,6 @@").replace(
            '+    return "new beginning"\n',
            '+    return "new beginning"\n+    inserted = True\n',
        )
    data_model.cmd_data_set(serve.page_dir, source, value(patch))
    told(page)
    rendered(page)
    assert page.evaluate("() => getSelection().toString()") == before, diff
    gutters = page.evaluate(
        """diff => {
      const widget = document.querySelector(diff);
      const entry = widget.fileEntries[0];
      return entry.lines.map(line => {
        const row = line.node.parentElement;
        const comment = row.querySelector('.lf-diff-line-comment');
        const number = String(line.side === 'old' ? line.oldLine : line.newLine);
        return {
          datum: line.node.dataset.lfDatum,
          commentInRow: comment.isConnected && comment.nextElementSibling === line.node,
          label: comment.textContent,
          expected: number,
          lineTypeMatches: row.dataset.lineType === line.node.dataset.lineType,
          commentCount: row.querySelectorAll('.lf-diff-line-comment').length,
        };
      });
    }""",
        diff,
    )
    assert all(
        gutter["commentInRow"]
        and gutter["label"] == gutter["expected"]
        and gutter["lineTypeMatches"]
        and gutter["commentCount"] == 1
        for gutter in gutters
    ), gutters


def test_a_closed_diff_file_reads_current_evidence_across_source_forms(browser, serve):
    """File disclosure keeps its owner and loads the current patch in either form: the
    evidence goes from a raw patch to a manifest while the file is closed, then back."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    code = page.locator("lf-diff code[data-code]").first
    code.evaluate("node => { node.scrollLeft = 200; }")
    summary = page.locator("lf-diff summary").first
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
    for words, form in (("new beginning", patch_manifest), ("new start", None)):
        summary.click()
        patch = MULTI_HUNK_PATCH.replace("new first", words)
        data_model.cmd_data_set(
            serve.page_dir, "review-patch", form(patch) if form else patch
        )
        told(page)
        rendered(page)
        summary.click()
        expect(row).to_contain_text(words)
        assert code.evaluate("node => node.scrollLeft") == 200, words


def test_a_diff_recovers_from_each_failure_on_the_next_good_source(browser, serve):
    """A diff shows each failure, a failed file's or the whole patch's, where the reader
    is looking, inside its shadow stage, and the next good source replaces it. A failed
    render cannot authorize reuse of the evidence its error removed."""
    url = serve(LONG_LINE_DIFF_PAGE)
    good = patch_manifest(MULTI_HUNK_PATCH)
    data_model.cmd_data_set(serve.page_dir, "review-patch", good)
    page = open_page(browser, url)
    failed_file = patch_manifest(MULTI_HUNK_PATCH)
    failed_file["files"][0]["patch"] = "invalid diff"
    repeated_path = MULTI_HUNK_PATCH + MULTI_HUNK_PATCH
    error = page.locator("lf-diff .lf-error")
    for bad in (failed_file, repeated_path, repeated_path):
        data_model.cmd_data_set(serve.page_dir, "review-patch", bad)
        told(page)
        rendered(page)
        expect(error).to_have_count(1)
        expect(error).to_be_visible()
        # Dressed as the failure box in the document is, not as plain text.
        expect(error).to_have_css("border-top-style", "solid")
        data_model.cmd_data_set(serve.page_dir, "review-patch", good)
        told(page)
        rendered(page)
        expect(error).to_have_count(0)
        expect(
            page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
        ).to_contain_text("new first")
    errors = consume_browser_errors(
        page, "failed: empty diff", "failed: unified diff repeats file path"
    )
    assert sum("failed: empty diff" in (said(error) or "") for error in errors) == 1
    assert (
        sum(
            "failed: unified diff repeats file path" in (said(error) or "")
            for error in errors
        )
        == 2
    )


def test_a_diff_file_keeps_focus_when_its_evidence_changes_kind(browser, serve):
    """A path keeps its controls; comment close and replaced evidence leave focus on its
    file: a raw patch that starts as a rename, and a manifest that starts as a change."""
    rename = (
        "diff --git a/old.py b/app/handlers.py\n"
        "similarity index 100%\nrename from old.py\nrename to app/handlers.py\n"
    )
    url = two_diff_page(serve)
    for (_, source, value), initial in zip(DIFF_FORMS, (rename, MULTI_HUNK_PATCH)):
        data_model.cmd_data_set(serve.page_dir, source, value(initial))
    page = open_page(browser, url)
    for form, starts_as_rename in zip(DIFF_FORMS, (True, False)):
        diff_file_keeps_focus(page, serve, *form, rename, starts_as_rename)


def diff_file_keeps_focus(page, serve, diff, source, value, rename, starts_as_rename):
    """Stand on `diff`'s first file, swap its evidence between a rename and a change
    and back, then change it while the file is closed."""
    regular = MULTI_HUNK_PATCH
    initial, other = (rename, regular) if starts_as_rename else (regular, rename)
    owner = page.locator(f"{diff} .lf-diff-file").first.element_handle()
    comment = page.locator(f"{diff} .lf-diff-file-comment").first.element_handle()
    if starts_as_rename:
        page.locator(f"{diff} .lf-diff-file-comment").first.click()
        page.keyboard.press("Escape")
        assert owner.evaluate("node => node === node.getRootNode().activeElement")
    else:
        page.locator(f"{diff} summary").first.click()
        page.keyboard.press("ArrowRight")
    scroll_settled(page)
    before = page.evaluate("() => scrollY")
    for patch in (other, initial):
        data_model.cmd_data_set(serve.page_dir, source, value(patch))
        told(page)
        rendered(page)
        assert owner.evaluate("node => node.isConnected")
        assert comment.evaluate("node => node.isConnected")
        assert owner.evaluate("node => node.contains(node.getRootNode().activeElement)")
        if starts_as_rename:
            assert owner.evaluate("node => node === node.getRootNode().activeElement")
        assert page.evaluate("() => scrollY") == before, diff
        if patch == regular:
            expect(
                page.locator(f'{diff} [data-lf-datum=\'["app/handlers.py","new",2]\']')
            ).to_contain_text("new first")
    if starts_as_rename:
        data_model.cmd_data_set(serve.page_dir, source, value(regular))
        told(page)
        rendered(page)
    summary = page.locator(f"{diff} summary").first
    summary.click()
    data_model.cmd_data_set(
        serve.page_dir, source, value(regular.replace("new first", "new beginning"))
    )
    told(page)
    rendered(page)
    summary.click()
    # The next form shares this page; finish this file's pointer fold first.
    summary.evaluate(
        "node => Promise.all(node.getRootNode().getAnimations()"
        ".filter(animation => animation.effect.target === node.parentElement"
        " && animation.effect.pseudoElement === '::details-content')"
        ".map(animation => animation.finished.catch(() => {})))"
    )
    expect(
        page.locator(f'{diff} [data-lf-datum=\'["app/handlers.py","new",2]\']')
    ).to_contain_text("new beginning")


def test_a_file_row_a_revision_brings_reads_its_cut_path(browser, serve):
    """A file that a revision turns from a rename into a changed file gets a new row,
    and that row, too, says whether it cuts its path short."""
    path = "plugins/worktrunk/skills/worktrunk/reference/config/deeply/handlers.py"
    rename = (
        f"diff --git a/old.py b/{path}\n"
        f"similarity index 100%\nrename from old.py\nrename to {path}\n"
    )
    regular = MULTI_HUNK_PATCH.replace("app/handlers.py", path)
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(rename))
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = open_page(browser, url, context=context)
    expect(page.locator("lf-diff .lf-diff-metadata")).to_have_count(1)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(regular))
    told(page)
    rendered(page)
    head = page.locator("lf-diff .lf-diff-head").first
    expect(head).to_have_attribute("data-path-cut", "")
    expect(head.locator(".lf-diff-path")).to_have_attribute("title", path)

    # A changed source path can retain exactly the old clipped width. Its title
    # must follow the new identity even when no size changes and the disclosure stays.
    head.evaluate("node => window.retainedDiffHead = node")
    for source in ("legacy/original.py", "legacy/previous.py"):
        changed_rename = (
            f"diff --git a/{source} b/{path}\nsimilarity index 50%\n"
            f"rename from {source}\nrename to {path}\n"
            f"--- a/{source}\n+++ b/{path}\n"
            "@@ -1 +1 @@\n-old()\n+new()\n"
        )
        data_model.cmd_data_set(
            serve.page_dir, "review-patch", patch_manifest(changed_rename)
        )
        told(page)
        rendered(page)
        expect(head.locator(".lf-diff-path")).to_have_attribute(
            "title", f"{source} → {path}"
        )
        assert head.evaluate("node => node === window.retainedDiffHead")


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_a_diff_revision_leaves_a_line_thread_where_it_stands(request, serve, engine):
    """A revision that redraws a thread's own line, and puts another file before its
    file, leaves the thread's outlet where it stands, so a frame in a reply keeps the
    document it loaded. Clearing the host's light DOM with `replaceChildren()` on each
    revision unloaded it in WebKit, which lacks `moveBefore` too."""

    def patch(path, body):
        return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{body}"

    first = patch("a.py", "@@ -1,3 +1,3 @@\n one\n-old\n+new\n three\n")
    url = serve(LONG_LINE_DIFF_PAGE)
    root = panel_comment(
        serve.page_dir, "Why?", {"section": "patch", "datum": '["a.py","new",2]'}
    )
    append_agent_reply(
        serve.page_dir,
        root,
        "Here is the plan.",
        '<iframe title="Plan" srcdoc="<p>The plan</p>"></iframe>',
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(first))
    page = open_page(request.getfixturevalue(engine), url)
    frame = page.locator("lf-diff .lf-diff-thread-outlet iframe")
    expect(frame).to_be_attached()
    frame.evaluate("""frame => new Promise(loaded => {
      const settle = () => {
        frame.contentWindow.lfKept = true;
        window.lfFrameLoads = 0;
        window.lfOutlet = frame.closest('.lf-diff-thread-outlet');
        frame.addEventListener("load", () => window.lfFrameLoads++);
        loaded();
      };
      if (frame.contentDocument?.readyState === "complete") settle();
      else frame.addEventListener("load", settle, {once: true});
    })""")
    redrawn = patch("0.py", "@@ -1 +1 @@\n-x\n+y\n") + first.replace("+new", "+newer")
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(redrawn))
    told(page)
    rendered(page)
    expect(
        page.locator('lf-diff [data-lf-datum=\'["a.py","new",2]\']')
    ).to_contain_text("newer")
    assert frame.evaluate(
        """frame => [frame.closest('.lf-diff-thread-outlet') === window.lfOutlet,
          frame.contentWindow?.lfKept, window.lfFrameLoads]"""
    ) == [True, True, 0]


@pytest.mark.parametrize("manifest, changes_kind", [(False, True), (True, False)])
def test_a_diff_refresh_leaves_an_inline_reply_to_its_thread_owner(
    browser, serve, manifest, changes_kind
):
    """A replacement carries its source focus; core carries the reply and its caret."""
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    next_patch = (
        "diff --git a/old.py b/a.py\nsimilarity index 100%\n"
        "rename from old.py\nrename to a.py\n"
        if changes_kind
        else patch.replace("+new\n", "+newer\n")
    )
    value = patch_manifest if manifest else lambda patch: patch
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(patch))
    page = open_page(browser, url)
    page.get_by_role("button", name="Comment on a.py · new line 1", exact=True).click()
    write(page.locator(".lf-composer leaf-text"), "Please clarify this.")
    with sending(page, "a line comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    reply = page.locator("lf-diff .lf-diff-thread-outlet .lf-thread-reply leaf-text")
    draft = "An unsent reader draft"
    write(reply, draft)
    page.keyboard.press("Home")
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    for _ in range(4):
        page.keyboard.press("Shift+ArrowRight")
    reading = "e => ({scroll: scrollY, value: e.value, start: e.selectionStart, end: e.selectionEnd})"
    before = reply.evaluate(reading)
    assert before["end"] - before["start"] == 4
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(next_patch))
    told(page)
    rendered(page)
    # The editor the user is located in. Chromium leaves an editor carried through a hidden
    # node unmatched by its own native `:focus-within` (notes/browser-support.md).
    current = page.locator(".lf-thread-reply leaf-text:focus")
    expect(current).to_have_js_property("value", draft)
    assert current.evaluate(reading) == before


def test_a_diff_disclosure_waits_for_the_source_render_that_owns_its_evidence(
    browser, serve
):
    """Opening a retained closed file joins a pending revision without a false error."""

    def patch(path, word):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{word}\n"
        )

    def value(word):
        return patch_manifest(patch("a.py", word) + patch("b.py", "second"))

    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("first"))
    page = open_page(browser, url)
    a = page.locator("lf-diff summary").nth(0)
    b = page.locator("lf-diff summary").nth(1)
    a.click()
    expect(page.locator('lf-diff [data-lf-datum=\'["a.py","new",1]\']')).to_have_text(
        "first"
    )
    b.click()
    line = page.locator('lf-diff [data-lf-datum=\'["b.py","new",1]\']')
    expect(line).to_have_text("second")
    b.click()
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("middle"))
    told(page)
    rendered(page)
    held = []

    def hold(route):
        if "key=a.py" in route.request.url:
            held.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/api/deferred*", hold)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("latest"))
    holding(page, held, 1, "the new open-file evidence")
    b.click()
    # Let the native toggle and its lazy load answer while the source revision is held.
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    try:
        assert page.locator("lf-diff .lf-error").count() == 0
    finally:
        for route, response in held:
            route.fulfill(response=response)
    rendered(page)
    expect(line).to_have_text("second")
    expect(page.locator('lf-diff [data-lf-datum=\'["a.py","new",1]\']')).to_have_text(
        "latest"
    )
    expect(page.locator("lf-diff .lf-error")).to_have_count(0)


# The line is one row split across syntax spans inside a shadow root, so the range is built
# over its text nodes rather than dragged: a pointer drag cannot reach words that are off
# the box in the state this starts in.
_SELECT_IN_ROW = """(row, phrase) => {
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    const nodes = [], starts = [];
    let flat = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      starts.push(flat.length); nodes.push(node); flat += node.data;
    }
    const start = flat.indexOf(phrase);
    if (start < 0) return null;
    const at = (offset) => {
      const index = starts.findLastIndex((value) => value <= offset);
      return [nodes[index], offset - starts[index]];
    };
    const range = document.createRange();
    range.setStart(...at(start));
    range.setEnd(...at(start + phrase.length));
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    // The row is a block, so it has one client rectangle however many line boxes are in
    // it, and its height is what says how many. Whether the words selected were on screen
    // is the range's own right edge against the file's scrolling box — not the row's,
    // which is sized to the longest line in the file so its fill reaches the end of it.
    const box = row.closest('code[data-code]').getBoundingClientRect();
    return { text: selection.toString(),
             height: Math.round(row.getBoundingClientRect().height),
             cut: range.getBoundingClientRect().right > box.right };
}"""


def test_a_diff_row_fills_to_the_end_of_its_line_and_to_the_end_of_a_narrow_box(
    browser, serve
):
    """A changed row says it changed by the colour behind it, and that colour is the row's
    own background, so it stops where the row's box stops. The renderer sizes the code
    column to the box that scrolls, which is the width the user could already see: on
    this patch the fill ran out 2,563px short of the line's end, so scrolling right left
    every addition and deletion sitting on the file's plain paper with nothing to say
    which it was.

    Every direction in one reading, because they are one track. The floor that carries the
    fill past the scrollport would, left alone, shrink a short file's rows to its own
    longest line and leave the rest of the box blank; and it measures whatever stands in
    that column, so a user's own remark would size the file too."""
    page = _bound_diff(browser, serve)

    filled = page.evaluate(DIFF_ROW_FILL)
    assert filled["rows"] > 20 and filled["scrolls"] > 0, (
        f"no file runs past its box, so a filled result would prove nothing: {filled}"
    )
    assert filled["short"] == 0, (
        f"a row's fill stops before its own text ends, worst by {filled['gap']}px: "
        f"{filled}"
    )
    assert filled["narrow"] == 0, f"a row's fill stops before its box does: {filled}"

    # A thread stands in the code column with the lines, and its prose unwrapped is far
    # wider than any of them, so the floor would take it for a line and size the file by
    # the longest remark. `app/routes.py` is what makes that reading sharp: its rows fit
    # their box, so a comment that reached the measure starts a file the user could see
    # whole scrolling sideways — 671px of rows in a 718px box became 796px in 843px.
    page.locator('lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']').evaluate(
        _SELECT_IN_ROW, "new route"
    )
    selection_field(page).click()
    write(
        page.locator(".lf-composer leaf-text"),
        "A remark of the ordinary length a reviewer writes, long enough that the line it "
        "would make unwrapped runs well past the longest line in this file, which is the "
        "whole of what the column is supposed to be measuring.",
    )
    with sending(page, "the comment on the short file's line"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("lf-diff .lf-diff-thread-outlet")).to_be_visible()

    remarked = page.evaluate(DIFF_ROW_FILL)
    assert remarked["scrolls"] == filled["scrolls"], (
        f"a remark sized the code, so a file that fit its box now scrolls: {remarked}"
    )
    assert (remarked["short"], remarked["narrow"]) == (
        0,
        0,
    ), f"the rows do not fill their box with a thread among them: {remarked}"


def test_print_wraps_diff_lines_and_keeps_file_headers_in_place(browser, serve):
    """Paper shows the complete long lines a reader reaches on screen by scrolling."""
    page = _bound_diff(
        browser,
        serve,
        MULTI_HUNK_PATCH + "\ndiff --git a/old.py b/new.py\nsimilarity index 100%\n"
        "rename from old.py\nrename to new.py\n",
    )
    expect(page.locator("lf-diff .lf-diff-metadata")).to_be_visible()

    cut = page.evaluate(DIFF_CLIPPING)
    assert cut["rows"] > 20, f"nothing to read: {cut}"
    assert cut["cut"] > 0 and cut["worst"] > 300, (
        f"no line runs past its box, so a wrapped result would prove nothing: {cut}"
    )
    # Which line, not just how many. The rows are all one width now — each is sized to the
    # longest line in its file so its fill reaches the end of it — so a reading taken off
    # the row's box rather than its text reports the file's overhang for every row alike
    # and still satisfies the count above. Naming the line is what tells the two apart.
    assert cut["widest"].strip().startswith('return "The comparison base'), (
        f"the reading does not name the line that overflows, so it is measuring the rows' "
        f"boxes rather than their text: {cut}"
    )

    placed = page.evaluate(DIFF_ROW_PLACEMENT)
    assert placed["files"] == 3 and (placed["lift"], placed["drop"]) == (
        0,
        0,
    ), f"a file's row does not start where its wrapper does: {placed}"
    page.emulate_media(media="print")
    printed = page.evaluate(DIFF_CLIPPING)
    on_paper = page.evaluate(DIFF_ROW_PLACEMENT)
    numbers = page.locator("lf-diff .lf-diff-line-comment").evaluate_all(
        """buttons => buttons.map(button => ({
          number: button.textContent,
          visible: button.checkVisibility(),
          plus: getComputedStyle(button, '::before').display,
        }))"""
    )
    assert len(numbers) == printed["rows"]
    assert all(
        number["visible"] and number["number"].isdigit() and number["plus"] == "none"
        for number in numbers
    ), numbers
    page.emulate_media(media="screen")
    assert printed["rows"] == cut["rows"], (printed, cut)
    assert printed["cut"] == 0, f"paper clipped a diff line: {printed}"
    assert on_paper["files"] == 3 and (on_paper["lift"], on_paper["drop"]) == (
        0,
        0,
    ), f"on paper a file's row is drawn above its own wrapper: {on_paper}"


def test_a_diff_keeps_the_file_named_while_its_hunks_go_past_and_lands_below_that_name(
    browser, serve
):
    """Two halves of one question — which file am I reading, and where did that press put
    me. The shipped review is 46 files and 32,000px: opening one and reading down it left
    nothing on screen saying whose lines these were, because the file's header stood in
    flow and scrolled away with its own first rows.

    Pinned, the header stands exactly at the root's sticky slot (`--lf-top`), the
    window's head where no chrome stands over it. A press then has to land past it:
    `scrollIntoView` reads the document's scroll-padding, which reserves that slot, and
    the header's own height is added to that as the rows' scroll-margin — measured,
    because a long path wraps and no stylesheet can work that number out.

    Reduced motion so the landing read is the product's and not the frame a smooth scroll
    happened to be on. The walk starts from the tools row, which belongs to no file, so
    the first `]` is the first hunk and the second is the step this test is about."""
    page = _bound_diff(browser, serve)
    page.emulate_media(reduced_motion="reduce")

    slot = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--lf-top'))"
    )
    in_flow = page.evaluate(DIFF_LANDING)
    assert in_flow["headTop"] > slot, (
        f"the header already meets the slot before anything scrolled: {in_flow}"
    )
    page.evaluate(
        """() => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('details');
            file.scrollIntoView({ block: 'start' });
            window.scrollBy(0, 200);
        }"""
    )
    pinned = page.evaluate(DIFF_LANDING)
    assert pinned["headTop"] == slot, f"the file's name is not at the slot: {pinned}"
    # The press drawn onto that line came with it. It stands outside the disclosure, so
    # nothing about the summary pinning moves it; placed against the file's top it stayed
    # there and scrolled off past the slot, leaving the pinned header's column empty
    # and the file comment out of reach for the whole of the file it names. Reached by a
    # pointer as well as measured, because a box can stand on the line and still be
    # painted under the header.
    press = page.evaluate(DIFF_PRESS)
    assert abs(press["top"] - (press["headTop"] + 5)) <= 2, (
        f"the comment press is not on the pinned header's line: {press}"
    )
    assert press["hit"] == "comment", (
        f"a pointer on the press reaches something else: {press}"
    )
    # And it leaves with the file. A sticky box is held inside its containing block by
    # its margin box, so a negative margin on the press lent it that much travel past
    # the file's end: with the header unpinned and gone, the press stood on for 32px of
    # scroll over the next file's header and that file's own press. Scrolled to where
    # the file's foot is 15px under the slot, the press's foot is no lower than
    # the file's.
    page.evaluate(
        """(slot) => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('.lf-diff-file').getBoundingClientRect();
            window.scrollBy(0, file.bottom - slot + 15);
        }""",
        slot,
    )
    leaving = page.evaluate(DIFF_PRESS)
    assert leaving["fileBottom"] < slot, (
        f"the file has not left the slot, so nothing is being measured: {leaving}"
    )
    assert leaving["bottom"] <= leaving["fileBottom"], (
        f"the comment press outlives its file: {leaving}"
    )
    page.evaluate("() => window.scrollTo(0, 0)")

    page.locator("lf-diff").evaluate("node => { node.tabIndex = -1; node.focus(); }")
    page.keyboard.press("]")
    first = page.evaluate(DIFF_LANDING)
    assert first["line"] == "1", f"the first hunk of the first file: {first}"
    expect_walk_says(page, "Hunk 1 of 3")

    page.keyboard.press("]")
    landed = page.evaluate(DIFF_LANDING)
    expect_walk_says(page, "Hunk 2 of 3")
    assert landed["line"] == "40", (
        f"the next hunk starts at new line 40, which its @@ header says: {landed}"
    )
    assert landed["path"] == "app/handlers.py", landed
    assert landed["top"] >= landed["headBottom"], (
        f"the row it landed on is behind the file's own pinned header: {landed}"
    )
    assert landed["headTop"] == slot, (
        f"the header is not pinned where the landing was measured against: {landed}"
    )
    page.keyboard.press("}")
    expect_walk_says(page, "File 2 of 2")
    page.keyboard.press("{")
    expect_walk_says(page, "File 1 of 2")


def test_tab_onto_a_seat_under_the_pinned_file_name_brings_it_out(browser, serve):
    """A thread seated in a diff stands in the code's sideways scroller, which starts
    the sticky-header slot again for whatever sticks inside it but lands nothing down,
    so the browser's own focus scroll still reads the file name pinned over the seat.
    Tab from the seat's reply field onto the control beside it, both under the pinned
    name, brings the control out from under it, where it had stayed hidden."""
    datum = json.dumps([LONG_DIFF_PATH, "new", 3], separators=(",", ":"))
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Seated", f"<h1>Seated</h1>{long_diff('patch')}" + "<p>.</p>" * 40
            ),
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Why this value?",
                    "anchor": {"section": "patch", "datum": datum},
                }
            ],
        ),
    )
    resized(page, 1280, 720)
    reply = page.locator("lf-diff .lf-diff-thread-outlet .lf-thread-reply leaf-text")
    expect(reply).to_be_visible()
    # The field just below the window's top, where the pinned name stands over it.
    reply.evaluate(
        "el => scrollBy({top: el.getBoundingClientRect().top - 4, behavior: 'instant'})"
    )
    scroll_settled(page)
    reply.evaluate("el => el.focus({preventScroll: true})")
    page.keyboard.press("Tab")
    rendered(page)
    read = page.evaluate(
        """() => {
        const root = document.getElementById('patch').shadowRoot;
        const head = root.querySelector('.lf-diff-file > details > summary');
        const seat = root.querySelector('.lf-diff-thread-outlet');
        const focused = root.activeElement;
        return {inSeat: seat.contains(focused), top: focused.getBoundingClientRect().top,
                head: head.getBoundingClientRect().bottom};
    }"""
    )
    assert read["inSeat"], read
    assert read["top"] >= read["head"], read


def test_a_diff_conversation_s_reply_rests_as_a_press_that_c_opens(browser, serve):
    """A conversation in a diff ends in a Reply press, one control high and with no
    frame or microphone, rather than an open field. A press opens the field, which
    rests again once the user leaves it empty, and `c` from the conversation opens it
    with the caret in it."""
    datum = json.dumps([LONG_DIFF_PATH, "new", 3], separators=(",", ":"))
    page = open_page(
        browser,
        serve(
            leaf_page("Seated", f"<h1>Seated</h1>{long_diff('patch')}"),
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Why this value?",
                    "anchor": {"section": "patch", "datum": datum},
                }
            ],
        ),
    )
    resized(page, 1280, 720)
    thread = page.locator("lf-diff .lf-diff-thread-outlet .lf-page-thread")
    reply = thread.get_by_role("textbox", name="Reply", exact=True)
    face = """field => {
      const box = field.parentElement;
      return {
        height: field.getBoundingClientRect().height,
        frame: getComputedStyle(box).borderTopColor,
        mic: getComputedStyle(box.querySelector('.lf-compose-dictate')).display,
      };
    }"""
    resting = {"height": 24, "frame": "rgba(0, 0, 0, 0)", "mic": "none"}
    expect(reply).to_be_visible()
    assert reply.evaluate(face) == resting
    reply.click()
    expect(reply).to_be_focused()
    opened = reply.evaluate(face)
    assert opened["height"] > resting["height"] and opened["mic"] != "none", opened
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    assert reply.evaluate(face) == resting
    thread.locator(".lf-msg-body").first.click()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    reached = reply.evaluate(face)
    assert (reached["height"], reached["mic"]) == (opened["height"], opened["mic"])
    page.keyboard.insert_text("Keep this draft open")
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    assert reply.evaluate(face)["height"] == opened["height"]
    expect(reply).to_have_js_property("value", "Keep this draft open")


def test_a_diff_in_a_pane_pins_the_file_name_at_the_pane_top_and_lands_below_it(
    browser, serve
):
    """The same two halves inside a full-height workspace pane, whose body is the box that
    scrolls the rows. The header used to stop the window's slot below the pane's top,
    because the offset it pinned at was the window's: rows scrolled past in the 42px
    above the name that headed them, and a `]` landing, which aligns to the pane's own
    top, put the row above its header. Where a sticking box stops is `--lf-top`, and a
    scrolling pane body declares it as its own top edge.

    Short enough a window that the patch overflows the pane, and still tall enough that
    the workspace holds it."""
    url = serve(PANE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1024, "height": 560})
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    page.emulate_media(reduced_motion="reduce")
    scrollport = """() => {
        const body = document.querySelector('lf-diff');
        return { top: Math.round(body.getBoundingClientRect().top),
                 scrolls: body.scrollHeight > body.clientHeight,
                 window: document.scrollingElement.scrollTop };
    }"""
    pane = page.evaluate(scrollport)
    assert pane["scrolls"], f"the patch fits its pane, so nothing can pin: {pane}"

    page.evaluate("() => { document.querySelector('lf-diff').scrollTop = 200; }")
    pinned = page.evaluate(DIFF_LANDING)
    assert pinned["headTop"] == pane["top"], (
        f"the file's name is not at the top of the pane that scrolls it: {pinned}, {pane}"
    )
    page.evaluate("() => { document.querySelector('lf-diff').scrollTop = 0; }")

    page.locator("lf-diff").evaluate("node => { node.tabIndex = -1; node.focus(); }")
    page.keyboard.press("]")
    page.keyboard.press("]")
    expect_walk_says(page, "Hunk 2 of 3")
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "40", landed
    assert landed["headTop"] == pane["top"], (
        f"the header is not pinned where the landing was measured against: {landed}"
    )
    assert landed["top"] >= landed["headBottom"], (
        f"the row it landed on is above or behind its file's pinned header: {landed}"
    )
    assert page.evaluate(scrollport)["window"] == 0, "the window scrolled, not the pane"
    # The landed row wears the band where it can be seen: inside the code box that clips
    # it and below the header pinned over the row above. Drawn outset, its sides fell
    # outside that box and its upper run under the header, and the row showed no ring.
    row_ring = page.evaluate(f"""() => {{
        const at = document.querySelector('lf-diff').shadowRoot.activeElement;
        return ({_RING_WITHIN})(at, at.closest('code'));
    }}""")
    # Its right run is the row's end, as far off as the file's longest line, which the
    # code box scrolls sideways to reach; the other three are on screen.
    inside = row_ring["inside"]
    assert row_ring["drawn"] and inside["top"] and inside["bottom"], row_ring
    # And the code box has not moved sideways. The row runs past the box, so a landing
    # that let the browser bring it "nearest" scrolled the box to the row's start, the
    # width of the line numbers over it, hiding every line's marker and first characters.
    assert row_ring["sideways"] == 0 and inside["left"], (
        f"the landing scrolled the file's lines sideways under their numbers: {row_ring}"
    )
    assert row_ring["top"] >= landed["headBottom"], (
        f"the landed row's ring runs under its file's pinned header: {row_ring}"
    )
    # The pane's body is a Tab stop because it scrolls, and it fills its pane, so its
    # band stays inside the pane: the pane draws it inset over the body's cell
    # (base.css), where outset on the body the workspace body clipped its right and
    # lower runs.
    # The selected row retargets document focus to this host. Leave it first so
    # focusing the host itself publishes a new location and its pane band.
    host = page.locator("lf-diff")
    host.evaluate("node => { node.blur(); node.focus(); }")
    expect(host).to_have_attribute("data-lf-focus", "")
    host_ring = page.evaluate(
        """() => {
          const host = document.querySelector('lf-diff');
          const pane = host.closest('[data-lf-reading-role="pane"]');
          const band = getComputedStyle(pane, '::after');
          return { focus: host.matches(':focus-visible'),
                   own: getComputedStyle(host).outlineStyle,
                   band: [band.outlineStyle, band.outlineWidth,
                          parseFloat(band.outlineOffset) + parseFloat(band.outlineWidth)] };
        }"""
    )
    assert host_ring["focus"] and host_ring["own"] == "none", host_ring
    assert host_ring["band"][:2] == ["solid", "2px"] and host_ring["band"][2] <= 0, (
        host_ring
    )


# Where an element's focus band falls, from its computed outline, and whether that box
# stays inside `frame`'s border box, which is what clips it or covers its edge.
_RING_WITHIN = """(el, frame) => {
    const s = getComputedStyle(el);
    const out = parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth);
    const box = el.getBoundingClientRect(), edge = frame.getBoundingClientRect();
    const ring = { top: box.top - out, left: box.left - out,
                   right: box.right + out, bottom: box.bottom + out };
    return { drawn: s.outlineStyle === 'solid' && s.outlineWidth === '2px',
             focus: el.matches(':focus-visible'), top: Math.round(ring.top),
             sideways: frame.scrollLeft,
             inside: { top: ring.top >= edge.top, left: ring.left >= edge.left,
                       right: ring.right <= edge.right,
                       bottom: ring.bottom <= edge.bottom } };
}"""


@pytest.mark.parametrize(
    "engine, hosts",
    [("browser", ("wide",)), ("webkit_browser", ("narrow", "wide"))],
    ids=["chromium", "webkit"],
)
def test_horizontal_wheel_reaches_the_diff_reader(
    request, serve, subtests, engine, hosts
):
    """A fitting code box lets horizontal input reach its enclosing reader in WebKit too.
    A narrow host scrolls its own code; a wide one fits it, so its reader scrolls."""
    patch = (
        "diff --git a/reading.py b/reading.py\n"
        "--- a/reading.py\n+++ b/reading.py\n@@ -1 +1 @@\n"
        '-return "The previous release remains available for inspection."\n'
        '+return "The current release remains available for inspection."\n'
    )
    source = leaf_page(
        "Nested patch reader",
        "<h1>Review</h1>"
        + "".join(
            f'<div id="reader-{host}" class="reader" data-bound="start">'
            f'<lf-diff id="patch-{host}"><pre>{patch}</pre></lf-diff></div>'
            for host in hosts
        ),
        head="<style>.reader { width: 500px; }"
        "#patch-wide { width: 1000px; } #patch-narrow { width: 300px; }</style>",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1000, 900)
    for host in hosts:
        with subtests.test(host=host):
            wide_host = host == "wide"
            code = page.locator(f"#patch-{host} code[data-code]")
            reader = page.locator(f"#reader-{host}") if wide_host else code
            reader.scroll_into_view_if_needed()
            assert reader.evaluate("el => el.scrollWidth > el.clientWidth")
            if wide_host:
                assert code.evaluate("el => el.scrollWidth === el.clientWidth")
            box = code.bounding_box()
            assert box is not None
            page.mouse.move(box["x"] + 120, box["y"] + 25)
            page.mouse.wheel(200, 0)
            page.wait_for_function(
                """host => { const patch = document.querySelector(`#patch-${host}`);
                const box = host === 'wide' ? document.querySelector('#reader-wide') :
                patch.shadowRoot.querySelector('code[data-code]'); return box.scrollLeft > 0; }""",
                arg=host,
            )
            assert reader.evaluate("el => el.scrollLeft") > 0


def test_a_diff_hunk_landing_preserves_sideways_reading_outside_its_shadow_tree(
    browser, serve
):
    """A hunk step moves vertically without travelling sideways through its host,
    from the host's start and from partway across it."""
    source = leaf_page(
        "Sideways patch",
        '<h1>Review</h1><div id="sideways">'
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>'
        "</div>",
        head="<style>#sideways { width: 500px; overflow: auto; }"
        "#patch { width: 1000px; }</style>",
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.keyboard.press("Tab")
    for left in (0, 150):
        page.locator("#patch summary").first.focus()
        page.locator("#sideways").evaluate(
            "(el, left) => { el.scrollLeft = left; }", left
        )
        before = page.locator("#sideways").evaluate("el => el.scrollLeft")
        assert before == left
        page.keyboard.press("]")
        expect_walk_says(page, "Hunk 1 of 3")
        scroll_settled(page)
        assert page.locator("#sideways").evaluate("el => el.scrollLeft") == before


def test_a_backward_hunk_step_from_the_diff_itself_opens_one_file_and_lands_in_it(
    browser, serve
):
    """The mirror of the first `]` above, from the same current location: nothing focused inside
    the diff. That is where an in-page link to the diff's own id leaves a user, since
    `focusDestination` focuses the host, and the diff's keys answer there because the
    scope climb starts at the focused node itself.

    Going forward, nothing-focused meant every hunk lay ahead and the walk stopped at the
    first. Going back it meant every hunk lay ahead too, so none lay behind: the walk ran
    through the whole list, opened each file and landed nowhere. A collapsed manifest
    already holds each parsed file's evidence, so this step must open only the last
    file and make no further request for it."""
    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest(MULTI_HUNK_PATCH),
    )
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    fetched = []
    page.on(
        "request",
        lambda request: (
            fetched.append(request.url) if "/api/deferred" in request.url else None
        ),
    )
    # Focused as `focusDestination` leaves a host that an in-page link named.
    page.evaluate(
        """() => {
            const diff = document.querySelector('lf-diff');
            diff.tabIndex = -1;
            diff.focus();
        }"""
    )
    assert page.evaluate("() => document.activeElement.localName") == "lf-diff"
    assert (
        page.evaluate(
            "() => document.querySelector('lf-diff').shadowRoot.activeElement"
        )
        is None
    ), "the current location in this test has no focus inside the diff"

    page.keyboard.press("[")
    page.wait_for_function(
        """() => {
            const at = document.querySelector('lf-diff').shadowRoot.activeElement;
            return at && at.dataset.line !== undefined;
        }"""
    )
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "200", f"the last file's last hunk starts at 200: {landed}"
    assert landed["path"] == "app/routes.py", landed
    opened = page.evaluate(
        "() => document.querySelector('lf-diff').shadowRoot"
        ".querySelectorAll('details[open]').length"
    )
    assert opened == 1, f"the step opened files it never reached: {opened} open"
    assert not fetched, f"opening parsed evidence fetched it again: {fetched}"


@pytest.mark.parametrize("renamed", [False, True])
def test_a_phone_keeps_the_diff_file_name_and_the_sticky_header_height(
    iphone, serve, renamed
):
    """The space reserved above a landed row clears its sticky file header. The
    basename remains readable on a phone; the title retains the complete path, and
    WebKit draws the whole path a row says while the keyboard stands on it."""
    path = "plugins/worktrunk/skills/worktrunk/reference/config.md"
    previous = (
        "legacy/worktrunk/skills/worktrunk/reference/original.md" if renamed else path
    )
    rename = (
        f"similarity index 50%\nrename from {previous}\nrename to {path}\n"
        if renamed
        else ""
    )
    patch = (
        f"diff --git a/{previous} b/{path}\n{rename}--- a/{previous}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    page = open_page(
        None,
        serve(
            leaf_page(
                "Phone header",
                '<h1>Review</h1><lf-diff id="patch"><pre>' + patch + "</pre></lf-diff>",
            )
        ),
        context=iphone,
    )
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    head = page.evaluate(
        """() => {
        const head = document.querySelector('lf-diff').shadowRoot
            .querySelector('summary');
        const path = head.querySelector('.lf-diff-path');
        const bases = [...path.querySelectorAll('.lf-diff-base')];
        const reading = {
            height: head.getBoundingClientRect().height,
            reserved: parseFloat(getComputedStyle(
                head.parentElement.querySelector('[data-line]')
            ).scrollMarginTop),
            title: path.title,
            bases: bases.map(base => ({text: base.textContent,
                cut: base.scrollWidth > base.clientWidth,
                width: base.getBoundingClientRect().width})),
            arrow: path.querySelector('.lf-diff-arrow')?.getBoundingClientRect().toJSON(),
            path: path.getBoundingClientRect().toJSON(),
        };
        return reading;
    }"""
    )
    page.keyboard.press("Shift")  # keyboard modality, so the focus below is visible
    page.locator("lf-diff .lf-diff-head").focus()
    said = page.locator("lf-diff .lf-diff-path").evaluate(
        """path => {
        const word = getComputedStyle(path, '::after');
        return [word.content.replace(/\\u200b/g, ''), parseFloat(word.width)];
    }"""
    )
    assert head["height"] == pytest.approx(head["reserved"], abs=0.5), head
    assert [base["text"] for base in head["bases"]] == (
        ["original.md", "config.md"] if renamed else ["config.md"]
    ), head
    if renamed:
        # Each basename has room before the stable arrow, even where two names
        # cannot fit in full beside the statistics.
        assert all(base["width"] > 40 for base in head["bases"]), head
        assert head["arrow"]["width"] > 0, head
        assert head["path"]["x"] < head["arrow"]["x"], head
        assert head["arrow"]["right"] < head["path"]["right"], head
    else:
        assert not head["bases"][0]["cut"], head
    assert head["title"] == (f"{previous} → {path}" if renamed else path), head
    assert path in said[0] and said[1] > 0, said


def test_a_file_row_says_its_whole_path_to_the_keyboard_and_a_held_finger(
    browser, serve
):
    """A file's row gives way from its folders, and its title reaches only a pointer
    resting on it. The keyboard location on the row, and a finger held on it, read the
    whole path in a box under the row, a folded file's too, over the next file's row.
    Releasing the hold folds the file, as a tap does. Touch focus keeps the path
    visible until it leaves. A row that shows its whole path at the width it has
    now shows no box and has no title."""
    path = "plugins/worktrunk/skills/worktrunk/reference/config/deeply/nested/file.md"
    patch = "".join(
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for name in (path, "src/next.rs")
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Phone header",
                '<h1>Review</h1><lf-diff id="patch"><pre>' + patch + "</pre></lf-diff>",
            )
        ),
        context=context,
    )
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    head = page.locator("lf-diff .lf-diff-head").first
    # The box is generated content, which takes no hit unless a rule lets it: this
    # test's own rule does, so a hit-test at the box's corner says what stands on top.
    head.evaluate("""head => {
        const sheet = new CSSStyleSheet();
        sheet.replaceSync('.lf-diff-path::after { pointer-events: auto !important; }');
        const root = head.getRootNode();
        root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
    }""")
    read = """head => {
        const path = head.querySelector('.lf-diff-path');
        const word = getComputedStyle(path, '::after');
        const at = head.getBoundingClientRect();
        const hit = word.content === 'none' ? null : head.getRootNode().elementFromPoint(
            at.left + head.clientLeft + parseFloat(word.left) + 6,
            at.top + head.clientTop + parseFloat(word.top) + 6,
        );
        return {
            open: head.parentElement.open,
            word: word.content === 'none' ? null
                : word.content.replace(/\\u200b/g, ''),
            shown: word.visibility === 'visible',
            below: parseFloat(word.top) >= at.height,
            fits: parseFloat(word.left) + parseFloat(word.width) <= at.width + 0.5,
            onTop: hit === path,
        };
    }"""
    whole = f'"{path}" / ""'
    assert head.evaluate(read)["word"] is None

    page.keyboard.press("Shift")  # keyboard modality, so the focus below is visible
    head.focus()
    focused = head.evaluate(read)
    assert focused == {
        "open": True,
        "word": whole,
        "shown": True,
        "below": True,
        "fits": True,
        "onTop": True,
    }, focused
    page.keyboard.press("Enter")
    assert head.evaluate(read) == {**focused, "open": False}
    page.keyboard.press("Enter")
    head.evaluate("head => head.blur()")

    cdp = context.new_cdp_session(page)
    box = head.bounding_box()
    point = {"x": round(box["x"] + box["width"] / 2), "y": round(box["y"] + 10)}

    def touch(kind):
        cdp.send(
            "Input.dispatchTouchEvent",
            {"type": kind, "touchPoints": [point] if kind != "touchEnd" else []},
        )

    touch("touchStart")
    rendered(page)
    expect(head).to_have_attribute("data-lf-held-word", "")
    page.wait_for_function(
        """() => getComputedStyle(document.querySelector('lf-diff').shadowRoot
            .querySelector('.lf-diff-path'), '::after').visibility === 'visible'"""
    )
    held = head.evaluate(read)
    assert held["word"] == whole and held["open"], held
    touch("touchEnd")
    rendered(page)
    assert head.evaluate(read)["open"] is False, "the release folds the file"
    expect(head).to_be_focused()
    expect(head).to_have_attribute("data-lf-focus", "")
    assert head.evaluate(read)["word"] == whole
    page.evaluate(RELEASE_FOCUS)
    assert head.evaluate(read)["word"] is None

    page.touchscreen.tap(point["x"], point["y"])
    rendered(page)
    assert head.evaluate(read)["open"] is True, "a tap unfolds it"
    expect(head).to_be_focused()
    expect(head).to_have_attribute("data-lf-focus", "")
    assert head.evaluate(read)["word"] == whole
    page.evaluate(RELEASE_FOCUS)
    assert head.evaluate(read)["word"] is None

    # A row that shows its whole path shows no box and has no title, and a row's box
    # and title follow the width the row is given while the keyboard stays on it.
    page.keyboard.press("Shift")
    titled = "head => head.querySelector('.lf-diff-path').getAttribute('title')"
    short = page.locator("lf-diff .lf-diff-head").nth(1)
    short.focus()
    assert short.evaluate(read)["word"] is None, "a short path is said twice"
    assert short.evaluate(titled) is None, "a short path's title repeats it"
    head.focus()
    assert head.evaluate(read)["word"] == whole and head.evaluate(titled) == path
    page.set_viewport_size({"width": 1400, "height": 844})
    rendered(page)
    assert head.evaluate(read)["word"] is None, "a path the row shows whole is said"
    assert head.evaluate(titled) is None
    page.set_viewport_size({"width": 390, "height": 844})
    rendered(page)
    assert head.evaluate(read)["word"] == whole, "a narrowed row hides its path"
    assert head.evaluate(titled) == path
