"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import _publish
from render_harness import (
    leaf_page,
    long_press,
    margins_laid_out,
    open_page,
    told,
)

from browser.threads import open_panel_thread
from leaf.render_checks import rendered

PREVIEW = "#lf-preview"
# Every box the thread draws, and the preview's own, where the page stands them.
BOXES = """() => [...document.querySelectorAll(
    '.lf-fp-view[data-lf-route=thread] *, .lf-fp-row *')]
  .filter((node) => node.checkVisibility())
  .map((node) => {
    const box = node.getBoundingClientRect();
    return [box.x, box.y, box.width, box.height].map(Math.round).join(',');
  })"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_control_previews_its_word_and_every_key_that_presses_it(
    engine, request, serve
):
    """A thread's Resolve shows its symbol, so its preview says its word and `r`, which
    presses it from anywhere in the thread, as a key chip: after a short rest of the
    pointer, at once under the keyboard's focus, and with no tooltip of the platform's
    beside it. The preview moves nothing, the pointer can cross onto it and read it
    there, and the next control the pointer reaches says its own at once. While it stands, Escape puts it away and does
    nothing else, so the thread it covers stays open; the next Escape leaves it."""
    url = serve(PANEL_PAGE)
    thread = panel_comment(serve.page_dir, "Could the mobile cohort wait a week?")
    page = open_page(request.getfixturevalue(engine), url)
    view = open_panel_thread(page, thread)
    resolve = page.locator(".lf-fp-thread-controls .lf-resolve")
    preview = page.locator(PREVIEW)
    expect(resolve).to_be_visible()
    # Off Leaf its word is the browser's tooltip; on Leaf it writes no title, so the
    # browser shows none beside the preview.
    assert resolve.get_attribute("title") is None, (
        "the browser's tooltip would show too"
    )
    rendered(page)
    before = page.evaluate(BOXES)

    resolve.hover()
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-preview-word")).to_have_text("Resolve thread")
    expect(preview.locator("kbd.lf-key-badge")).to_have_text(["r"])
    # The chip's key is the one a screen reader hears it has.
    assert "r" in resolve.get_attribute("aria-keyshortcuts").split()
    rendered(page)
    assert page.evaluate(BOXES) == before, "showing the preview moved the thread"
    tip = preview.bounding_box()
    # The pointer onto the preview keeps it, and reads it there (WCAG 1.4.13).
    page.mouse.move(tip["x"] + tip["width"] / 2, tip["y"] + tip["height"] / 2)
    page.wait_for_timeout(400)
    expect(preview.locator(".lf-preview-word")).to_have_text("Resolve thread")

    close = page.locator(".lf-fp-head .lf-fp-close")
    close.hover()
    expect(preview.locator(".lf-preview-word")).to_have_text(
        close.get_attribute("aria-label")
    )
    page.mouse.move(0, 0)
    expect(preview).to_be_hidden()

    # The keyboard's focus reads it at once, and Escape hides it.
    resolve.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(resolve).to_be_focused()
    expect(preview.locator("kbd.lf-key-badge")).to_have_text(["r"])
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    expect(resolve).to_be_focused()
    expect(view).to_be_visible()
    page.keyboard.press("Escape")
    expect(view).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_range_previews_beside_the_line_the_pointer_rests_on(engine, request, serve):
    """A range with no element of its own, as a passage mark is, previews through its
    owner's word of where the pointer rests: beside the line pointed at, carried with it
    through a scroll, and gone a dwell after the pointer leaves the range. An owner that makes the
    range again on every move points at the same range, so the dwell runs out once."""
    words = " ".join(["The passage runs across more than one line of the column."] * 6)
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page("Ranges", f'<p id="passage">{words}</p>' + "<p>More.</p>" * 40)
        ),
    )
    reading = page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const text = document.getElementById('passage').firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, text.length);
          const lines = [...range.getClientRects()];
          const line = lines[1];
          const tip = document.getElementById('lf-preview');
          const started = performance.now();
          while (!tip.matches(':popover-open') && performance.now() - started < 2000) {
            pointRange(range.cloneRange(), () => ({name: 'Its thread'}),
              {x: line.left + 2, y: line.top + line.height / 2});
            await new Promise((done) => setTimeout(done, 20));
          }
          const box = tip.getBoundingClientRect();
          scrollBy(0, 30);
          // Firefox carries an anchored box after its own scroll a frame or two late
          // under load.
          const offset = () => tip.getBoundingClientRect().top
            - range.getClientRects()[1].bottom;
          for (let n = 0; n < 10 && Math.abs(offset() - (box.top - line.bottom)) >= 1; n++)
            await new Promise(requestAnimationFrame);
          const carried = offset();
          pointRange(null);
          const leaving = tip.matches(':popover-open');
          await new Promise((done) => setTimeout(done, 400));
          return {text: tip.innerText, gap: box.top - line.bottom, left: box.left - line.left,
            carried, leaving, open: tip.matches(':popover-open')};
        }"""
    )
    assert reading["text"] == "Its thread"
    assert reading["gap"] > 0 and reading["left"] == 0, reading
    assert abs(reading["carried"] - reading["gap"]) < 1, "the scroll left it behind"
    # It waits a dwell, as the pointer may be on its way onto the preview.
    assert reading["leaving"], "the preview went before the pointer could reach it"
    assert not reading["open"], "the preview stayed once the pointer left the range"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_shown_on_focus_describes_what_focus_is_on(engine, request, serve):
    """A screen reader hears a preview the keyboard's focus shows as the focused
    element's description while it stands, whatever supplied it, and the element's own
    description is back once focus leaves: a margin entry's, which its label declares."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Which command?", {"section": "lede"})
    page = open_page(request.getfixturevalue(engine), url)
    entry = page.locator('[data-lf-margin-for="lede"] .lf-margin-marker')
    expect(entry).to_be_visible()
    rendered(page)
    described = "(node) => (node.ariaDescribedByElements ?? []).map((el) => el.id)"
    # The user steps onto the entry themselves: Tab and back.
    page.keyboard.press("Shift")
    entry.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(entry).to_be_focused()
    expect(page.locator(PREVIEW)).to_have_attribute("data-lf-route", "focus")
    assert "lf-preview" in entry.evaluate(described)
    page.keyboard.press("Tab")
    expect(entry).not_to_be_focused()
    assert entry.get_attribute("aria-describedby") is None


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_preview_redraws_in_place_when_its_element_says_it_changed(
    engine, request, serve
):
    """An element whose aim moves inside it, as a chart's point does, says its preview
    changed (`previewChanged`): the preview standing for it reads the element again and
    draws the new words where it stands, still open, for a resting pointer and for the
    keyboard's focus."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Points",
                '<p><span id="value" tabindex="0">A value</span></p>'
                + "<p>More.</p>" * 5,
            )
        ),
    )
    page.evaluate(
        """() => {
          window.lfPoint = 1;
          document.getElementById('value').lfPreview = () =>
            ({name: `Point ${window.lfPoint}`});
        }"""
    )
    value = page.locator("#value")
    tip = page.locator(PREVIEW)
    moved = """async () => {
      const {previewChanged} = await window.__lfWidgetApi();
      window.lfPoint += 1;
      previewChanged(document.getElementById('value'));
    }"""

    page.mouse.move(2, 2)
    value.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 1")
    page.evaluate(moved)
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 2")
    rendered(page)
    expect(tip).to_be_visible()

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.keyboard.press("Shift")
    value.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 2")
    page.evaluate(moved)
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 3")
    rendered(page)
    expect(tip).to_be_visible()


def test_a_standing_preview_reads_its_element_again_as_the_page_presents_news(
    browser, serve
):
    """A preview standing when the page presents a new state reads its element again,
    so it says what holds now without its declaration tracking what it reads, as a
    link's place or a thread's turn changes under it, and stays open where it stands."""
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.evaluate(
        """() => {
          window.lfWords = 'Before the news';
          document.querySelector('#lede').lfPreview = () => ({name: window.lfWords});
        }"""
    )
    lede = page.locator("#lede")
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    lede.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Before the news")
    page.evaluate("() => { window.lfWords = 'After the news'; }")
    panel_comment(serve.page_dir, "News the page presents.")
    told(page)
    expect(tip.locator(".lf-preview-word")).to_have_text("After the news")
    expect(tip).to_be_visible()


def test_a_standing_range_preview_says_its_owners_latest_words(browser, serve):
    """A range's preview standing while what its owner says about it changes, as a
    thread turning to the user's under its passage, says the new words with no pointer
    input: on the page's next presentation, and when the owner declares the same range
    again with other words."""
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    tip = page.locator(PREVIEW)
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const text = document.getElementById('lede').firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, 8);
          const line = range.getClientRects()[0];
          window.lfWords = '2 messages';
          window.lfRange = range;
          window.lfAt = {x: line.left + 2, y: line.top + line.height / 2};
          pointRange(range, () => ({name: window.lfWords}), window.lfAt);
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("2 messages")

    page.evaluate("() => { window.lfWords = '3 messages · your turn'; }")
    panel_comment(serve.page_dir, "News the page presents.")
    told(page)
    expect(tip.locator(".lf-preview-word")).to_have_text("3 messages · your turn")

    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          pointRange(window.lfRange.cloneRange(), () => ({name: 'Resolved'}), window.lfAt);
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("Resolved")
    expect(tip).to_be_visible()


def test_a_standing_preview_says_what_a_new_revision_changed(browser, serve):
    """A preview standing over a link while a new revision changes the place it points
    at says the place's new words, with no pointer input: a revision ends in a
    presentation, which reads every standing preview again."""

    def page_with(words):
        return leaf_page(
            "Revisions",
            '<p><span id="go" tabindex="0">The table below</span></p>'
            f'<p id="dest">{words}</p>' + "<p>More.</p>" * 4,
        )

    url = serve(page_with("The first words"))
    page = open_page(browser, live_url(url))
    page.evaluate(
        """() => {
          document.getElementById('go').lfPreview = () =>
            ({name: document.getElementById('dest').textContent});
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#go").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("The first words")
    _publish(serve.page_dir, 2, page_with("The revised words"), "two")
    told(page)
    expect(page.locator("#dest")).to_have_text("The revised words")
    expect(tip.locator(".lf-preview-word")).to_have_text("The revised words")
    expect(tip).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_innermost_target_previews_on_every_route(engine, request, serve):
    """A link inside a passage a range's owner previews, as a link in a commented
    paragraph, previews as the link: to a resting pointer, though the passage's owner
    reports its range under the pointer after the link's boundary, as to the keyboard
    and a finger. The passage's words around the link still preview as the passage."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Innermost",
                '<p id="passage">The words a thread is about, with '
                '<a id="go" href="#more">a link</a> among them, and more words after '
                "the link so the passage runs on.</p>"
                + '<p id="more">More.</p>'
                + "<p>More words.</p>" * 3,
            )
        ),
    )
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const passage = document.getElementById('passage');
          document.getElementById('go').lfPreview = () => ({name: 'The link'});
          const range = document.createRange();
          range.selectNodeContents(passage);
          passage.addEventListener('pointermove', (event) =>
            pointRange(range.cloneRange(), () => ({name: 'The thread'}),
              {x: event.clientX, y: event.clientY}));
          passage.addEventListener('pointerleave', () => pointRange(null));
        }"""
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    box = page.locator("#passage").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 8, steps=4)
    expect(word).to_have_text("The thread")
    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    link = page.locator("#go").bounding_box()
    page.mouse.move(link["x"] + 4, link["y"] + link["height"] / 2, steps=4)
    page.mouse.move(link["x"] + 8, link["y"] + link["height"] / 2, steps=2)
    expect(word).to_have_text("The link")


# How many times the margin lays out (`lf-margin-layout`) and which of the page's boxes
# are written from now until `window.lfHeard()` is awaited, two frames on: a style or
# class written on a page box is what brings a pass (margin-layout.js, `heardPage`). The
# preview's own boxes are not the page's.
HEARD = """() => {
  const stage = document.getElementById('lf-preview').parentElement;
  const heard = {marginPasses: 0, written: new Set()};
  const passed = () => { heard.marginPasses += 1; };
  document.addEventListener('lf-margin-layout', passed);
  const watch = new MutationObserver((records) => {
    for (const record of records)
      if (!stage.contains(record.target))
        heard.written.add(record.target.id || record.target.localName);
  });
  watch.observe(document.documentElement,
    {subtree: true, attributes: true, attributeFilter: ['style', 'class']});
  window.lfHeard = async () => {
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
    watch.disconnect();
    document.removeEventListener('lf-margin-layout', passed);
    return {marginPasses: heard.marginPasses, written: [...heard.written]};
  };
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_writes_nothing_on_the_page(engine, request, serve):
    """A preview shows with its target as its source and the browser places it, so it
    writes nothing on the page's boxes, its root or a box that scrolls its target,
    which the margin would hear as a change and lay out again: the session's first
    preview, a range's on a paragraph, and the first inside an authored scroller. The
    pointer comes from words beside each target, so its travel reads nothing either."""
    url = serve(
        leaf_page(
            "Quiet previews",
            '<p id="lede">A paragraph a thread is about.</p>'
            '<div id="box" style="height: 80px; overflow: auto">'
            '<p><span id="calm">Calm words</span> '
            '<button id="inner" aria-label="A control in a scroller">⚙</button></p>'
            '<p style="height: 200px">More.</p></div>',
        )
    )
    panel_comment(serve.page_dir, "About the lede.", {"section": "lede"})
    page = open_page(request.getfixturevalue(engine), url)
    expect(
        page.locator('[data-lf-margin-for="lede"] .lf-margin-marker')
    ).to_be_visible()
    tip = page.locator(PREVIEW)
    margins_laid_out(page)
    rendered(page)
    page.evaluate(HEARD)
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const range = document.createRange();
          range.selectNodeContents(document.getElementById('lede'));
          const line = range.getClientRects()[0];
          pointRange(range, () => ({name: 'Its thread'}),
            {x: line.left + 2, y: line.top + 4});
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("Its thread")
    assert page.evaluate("window.lfHeard()") == {"marginPasses": 0, "written": []}
    page.evaluate("async () => (await window.__lfCheckApi()).pointRange(null)")
    expect(tip).to_be_hidden()

    page.locator("#calm").hover()
    margins_laid_out(page)
    rendered(page)
    page.evaluate(HEARD)
    page.locator("#inner").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("A control in a scroller")
    assert page.evaluate("window.lfHeard()") == {"marginPasses": 0, "written": []}


GRID = """<div id="grid" style="display: grid; grid-template-columns: repeat(2, max-content);
  gap: 4px"><button id="g-a" aria-label="Alpha control">A</button><button id="g-b"
  aria-label="Bravo control">B</button><button id="g-c" aria-label="Charlie control">C
  </button><button id="g-d" aria-label="Delta control">D</button></div>
<dialog id="dialog"><p>In the dialog.</p>
  <button id="in-dialog" aria-label="A control in the dialog">⚙</button></dialog>"""
# Where the preview stands, and which of `ids` it covers.
COVERS = """(ids) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  return ids.filter((id) => {
    const box = document.getElementById(id).getBoundingClientRect();
    return box.left < tip.right && tip.left < box.right && box.top < tip.bottom
      && tip.top < box.bottom;
  });
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_covers_no_neighbour_and_takes_the_pointer_in_a_modal(
    engine, request, serve
):
    """In a grid of controls a preview stands where it covers none of the neighbours,
    so the pointer reaches the one below and reads that one's preview, and inside a
    modal dialog the preview stands in the dialog, so the pointer can cross onto it and
    read it there, where outside it the dialog would make it inert."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Neighbours", "<p>Words above the grid.</p>" * 6 + GRID)),
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    page.locator("#g-a").hover()
    expect(word).to_have_text("Alpha control")
    assert page.evaluate(COVERS, ["g-b", "g-c", "g-d"]) == []
    below = page.locator("#g-c").bounding_box()
    page.mouse.move(
        below["x"] + below["width"] / 2, below["y"] + below["height"] / 2, steps=6
    )
    expect(word).to_have_text("Charlie control")

    page.mouse.move(2, 2)
    page.evaluate("() => document.getElementById('dialog').showModal()")
    page.locator("#in-dialog").hover()
    expect(word).to_have_text("A control in the dialog")
    box = tip.bounding_box()
    middle = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
    page.mouse.move(*middle, steps=4)
    page.wait_for_timeout(400)
    expect(word).to_have_text("A control in the dialog")
    assert page.evaluate(
        "([x, y]) => Boolean(document.elementFromPoint(x, y)?.closest('#lf-preview'))",
        middle,
    ), "the dialog left the preview inert"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_put_away_stays_away_until_the_user_aims_again(
    engine, request, serve
):
    """Escape puts a focus preview away, and an element declaring its preview again,
    as a chart redrawing with the same point does, brings nothing back; nor does a
    grip whose words come back once its card is put down. The element hears that its
    preview ended (`PREVIEW_ENDED`). A widget placing focus as a move after a
    microtask shows it, since the cause is the placement's, and the user stepping
    back with the keyboard shows it again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Put away",
                '<p><button id="before">Before</button> '
                '<span id="chart" tabindex="0">A chart</span> '
                '<span id="grip" tabindex="0">A grip</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          window.lf = {point: 1, held: false, ended: 0};
          const chart = document.getElementById('chart');
          chart.lfPreview = () => ({name: `Point ${window.lf.point}`});
          chart.addEventListener('lf-preview-ended', () => { window.lf.ended += 1; });
          document.getElementById('grip').lfPreview = () =>
            !window.lf.held && {name: 'Drag to move'};
        }"""
    )
    changed = """async (id) => {
      const {previewChanged} = await window.__lfWidgetApi();
      previewChanged(document.getElementById(id));
    }"""
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Point 1")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    assert page.evaluate("window.lf.ended") == 1
    page.evaluate("() => { window.lf.point = 2; }")
    page.evaluate(changed, "chart")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()
    # A new point aimed at inside it is a new target, which shows again.
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          window.lf.point = 3;
          previewChanged(document.getElementById('chart'), {aim: true});
        }"""
    )
    expect(tip).to_have_text("Point 3")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate("() => { window.lf.point = 2; }")

    page.keyboard.press("Tab")
    expect(tip).to_have_text("Drag to move")
    page.evaluate("() => { window.lf.held = true; }")
    page.evaluate(changed, "grip")
    expect(tip).to_be_hidden()
    page.evaluate("() => { window.lf.held = false; }")
    page.evaluate(changed, "grip")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()

    page.keyboard.press("Shift+Tab")
    expect(tip).to_have_text("Point 2")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate(
        """async () => {
          const {focusDestination} = await import('/runtime/focus.js');
          document.getElementById('before').focus();
          queueMicrotask(() =>
            focusDestination(document.getElementById('chart'), 'move'));
        }"""
    )
    expect(tip).to_have_text("Point 2")
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(tip).to_have_text("Point 2")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_title_stays_its_writers(engine, request, serve):
    """A title is its writer's: a pointer over it reads the browser's tooltip and no
    preview, focus reads its words in the preview, and nothing takes the attribute
    off, so a title removed leaves no words behind and a control it names keeps its
    name."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Titles",
                '<p><button id="before">Before</button> '
                '<span id="titled" tabindex="0" title="The author\'s words">Words</span> '
                '<button id="named" title="Named by its title">'
                '<span aria-hidden="true">⚙</span></button></p>',
            )
        ),
    )
    tip = page.locator(PREVIEW)
    titled = page.locator("#titled")
    page.mouse.move(2, 2)
    titled.hover()
    page.wait_for_timeout(500)
    expect(tip).to_be_hidden()
    expect(titled).to_have_attribute("title", "The author's words")
    page.mouse.move(2, 2)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("The author's words")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Named by its title")).to_be_focused()
    expect(tip).to_have_text("Named by its title")

    page.evaluate("() => document.activeElement.blur()")
    expect(tip).to_be_hidden()
    page.evaluate("() => document.getElementById('titled').removeAttribute('title')")
    titled.hover()
    page.wait_for_timeout(500)
    expect(tip).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_stands_by_its_target_as_the_page_moves(engine, request, serve):
    """The browser stands a preview by its target: through a scroll inside the page
    and a resize of the window, from a right-to-left target's right edge, and, taller
    than the room on either side once the window shrinks, held to the room it has with
    the lines that fit, the last ending in an ellipsis."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Standing",
                '<p><button id="before">Before</button></p>'
                '<div id="box" tabindex="-1" style="height: 120px; width: 320px; overflow: auto">'
                '<p style="padding-top: 40px"><span id="inner" tabindex="0">Inner</span>'
                '</p><p style="height: 400px">More.</p></div>'
                '<p dir="rtl" style="margin-inline-start: 200px">מילים עם '
                '<span id="rtl" tabindex="0">קישור</span> ועוד מילים</p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          document.getElementById('inner').lfPreview = () => ({name: 'Inner value'});
          document.getElementById('rtl').lfPreview = () => ({name: 'A name in full'});
        }"""
    )
    tip = page.locator(PREVIEW)
    beside = """(id) => {
      const tip = document.getElementById('lf-preview').getBoundingClientRect();
      const at = document.getElementById(id).getBoundingClientRect();
      return {start: Math.round(tip.left - at.left), end: Math.round(at.right - tip.right),
        gap: Math.round(tip.top - at.bottom), top: Math.round(tip.top),
        bottom: Math.round(tip.bottom), window: innerHeight,
        cut: Boolean(document.querySelector('#lf-preview [data-lf-cut]')),
        hidden: [...document.querySelectorAll('#lf-preview .lf-preview-detail')]
          .filter((line) => getComputedStyle(line).visibility === 'hidden').length};
    }"""
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Inner value")
    shown = page.evaluate(beside, "inner")
    page.evaluate("() => { document.getElementById('box').scrollTop = 25; }")
    page.wait_for_timeout(200)
    assert page.evaluate(beside, "inner")["gap"] == shown["gap"], "the scroll left it"
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"] - 200, "height": size["height"]})
    page.wait_for_timeout(300)
    resized = page.evaluate(beside, "inner")
    # The window's resize places it again, by the same gap, on whichever side then
    # holds it and covers no other target.
    assert resized["gap"] == shown["gap"], (resized, shown)
    page.set_viewport_size(size)

    rtl = page.locator("#rtl")
    rtl.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(tip).to_have_text("A name in full")
    assert page.evaluate(beside, "rtl")["end"] == 0, "it starts at the left edge"

    page.evaluate(
        """() => { document.getElementById('inner').lfPreview = () => ({name: 'Many',
          detail: Array.from({length: 30}, (_, i) => `Line ${i + 1} of its detail`)}); }"""
    )
    page.evaluate("() => document.getElementById('box').scrollTop = 0")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Many")
    page.set_viewport_size({"width": size["width"], "height": 260})
    page.wait_for_timeout(400)
    held = page.evaluate(beside, "inner")
    assert held["top"] >= 0 and held["bottom"] <= held["window"], held
    # No preview scrolls: the lines that fit show, the last ending in an ellipsis.
    assert held["cut"] and held["hidden"] > 0, held


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_list_preview_shows_what_its_room_holds_and_counts_the_rest(
    engine, request, serve
):
    """A preview's list longer than the room its face is held to shows the items that
    fit and, under them, its declaration's words for how many more there are, the
    rest hidden from sight and from a screen reader; the window growing shows them
    all again, with no count."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Lists",
                '<p><button id="before">Before</button> '
                '<span id="place" tabindex="0">Threads here</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => { document.getElementById('place').lfPreview = () => ({
          name: '30 threads',
          list: {items: Array.from({length: 30}, (_, i) => `Thread ${i + 1}`),
            more: (count) => `and ${count} more threads`}}); }"""
    )
    tip = page.locator(PREVIEW)
    read = """() => {
      const tip = document.getElementById('lf-preview');
      const more = tip.querySelector('.lf-preview-more');
      const items = [...tip.querySelectorAll('.lf-preview-item')];
      const box = tip.getBoundingClientRect();
      const counted = getComputedStyle(more).visibility === 'visible';
      const end = counted ? more.getBoundingClientRect().top : box.bottom;
      return {seen: items.filter((item) => getComputedStyle(item).visibility === 'visible'
          && item.getBoundingClientRect().bottom <= end + 1).length,
        hidden: items.filter((item) => getComputedStyle(item).visibility === 'hidden')
          .length,
        more: counted ? more.textContent : null, inside: box.bottom <= innerHeight};
    }"""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 260})
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("30 threads")
    short = page.evaluate(read)
    assert 0 < short["seen"] < 30 and short["seen"] + short["hidden"] == 30, short
    assert short["more"] == f"and {short['hidden']} more threads", short
    assert short["inside"], short
    page.set_viewport_size({"width": size["width"], "height": 1400})
    page.wait_for_timeout(400)
    tall = page.evaluate(read)
    assert tall["hidden"] == 0 and tall["more"] is None, tall


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_stands_where_it_covers_no_small_target_and_fits_any_window(
    engine, request, serve
):
    """The side a preview takes is tested across the box the browser draws, every few
    pixels, so a control as small as WCAG's least target, 24 px, standing under the
    middle of the room below its target, sends it to a free side, and the box drawn
    covers none of them. In a window shorter than the preview, shorter than a few
    lines, it holds itself inside the window with the lines that fit."""
    rows = "".join(
        f'<button class="small" id="s{i}" aria-label="Small {i}" '
        f'style="position: absolute; left: {x}px; top: {y}px; width: 24px; height: 24px; '
        'padding: 0">·</button>'
        for i, (x, y) in enumerate(
            [(1100 + dx, 140 + dy) for dx in (40, 110, 180) for dy in (8, 40)]
        )
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Small targets",
                '<p><button id="before">Before</button></p>'
                '<button id="aim" style="position: absolute; left: 1100px; top: 100px" '
                'aria-label="Aimed at, with a name that runs on for a while">⚙</button>'
                + rows,
            )
        ),
    )
    tip = page.locator(PREVIEW)
    aim = page.locator("#aim")
    page.mouse.move(2, 2)
    aim.hover()
    expect(tip.locator(".lf-preview-word")).to_contain_text("Aimed at")
    covered = page.evaluate(
        """() => {
          const tip = document.getElementById('lf-preview').getBoundingClientRect();
          return [...document.querySelectorAll('.small')].filter((el) => {
            const box = el.getBoundingClientRect();
            return box.left < tip.right && tip.left < box.right && box.top < tip.bottom
              && tip.top < box.bottom;
          }).map((el) => el.id);
        }"""
    )
    assert covered == [], covered

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.evaluate(
        """() => { document.getElementById('aim').lfPreview = () => ({name: 'Many',
          detail: Array.from({length: 12}, (_, i) => `Line ${i + 1} of its detail`)}); }"""
    )
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 150})
    page.evaluate(
        "() => document.getElementById('aim').scrollIntoView({block: 'center'})"
    )
    aim.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Many")
    held = page.evaluate(
        """() => {
          const box = document.getElementById('lf-preview').getBoundingClientRect();
          return {top: box.top, bottom: box.bottom, window: innerHeight,
            cut: Boolean(document.querySelector('#lf-preview [data-lf-cut]'))};
        }"""
    )
    assert held["top"] >= 0 and held["bottom"] <= held["window"] and held["cut"], held


def test_focus_a_command_places_in_a_surface_it_opens_shows_no_preview(browser, serve):
    """`m` walks to the question waiting on the user and opens its card with focus in
    it: the card placed that focus as it opened, so nothing previews until the user
    moves on, as Tab inside the card does. Every element the walk focuses previews
    here, so a preview the placement showed would show."""
    url = serve(PANEL_PAGE)
    panel_comment(
        serve.page_dir,
        "Which day suits the launch?",
        {"section": "lede"},
        author="agent",
        obligation=True,
    )
    page = open_page(browser, url)
    page.evaluate(
        """() => document.addEventListener('focusin', (event) => {
          const el = event.composedPath()[0];
          if (el instanceof Element && !el.lfPreview)
            el.lfPreview = () => ({name: 'Placed here'});
        }, true)"""
    )
    tip = page.locator(PREVIEW)
    page.locator("body").focus()
    page.keyboard.press("m")
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Placed here")


def test_a_finger_s_hold_reads_and_its_release_presses_nothing(browser, serve):
    """A finger held on a target reads its preview at the platform's own long press,
    which its engine says (`contextmenu`), and the platform's menu stays shut; letting go
    presses nothing, the browser's own click after the release included: a held link
    stays where it is, and its preview stands until the next touch, which puts it away.
    An engine that says nothing as a press grows long, as WebKit's touch engines don't
    (`GestureEvent`), reads after `HOLD` instead. A press the platform never calls long
    is a tap, however slow, which shows nothing and follows the link."""
    url = serve(
        leaf_page(
            "Held link",
            '<p><a id="go" href="#far">a link</a> to read before following.</p>'
            + "<p>More.</p>" * 3
            + '<p id="far">Far.</p>',
        )
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.evaluate(
        """() => { document.getElementById('go').lfPreview = () =>
          ({name: 'Where it goes'}); }"""
    )
    cdp = context.new_cdp_session(page)
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    box = page.locator("#go").bounding_box()
    point = {"x": box["x"] + 10, "y": box["y"] + box["height"] / 2}
    elsewhere = page.locator("#far").bounding_box()

    def touch(kind, at=point):
        cdp.send(
            "Input.dispatchTouchEvent",
            {"type": kind, "touchPoints": [at] if kind != "touchEnd" else []},
        )

    def put_away():
        touch("touchStart", {"x": elsewhere["x"] + 10, "y": elsewhere["y"] + 4})
        touch("touchEnd")
        expect(tip).to_be_hidden()

    touch("touchStart")
    page.wait_for_timeout(600)
    expect(tip).to_be_hidden()
    assert long_press(page, point) is False, "the platform's menu opened"
    expect(tip).to_be_visible()
    expect(word).to_have_text("Where it goes")
    expect(tip).to_have_attribute("data-lf-route", "hold")
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == "", "the held link was followed"
    expect(tip).to_be_visible()
    expect(page.locator("#go")).to_have_attribute("data-lf-held", "")
    put_away()

    page.evaluate("() => { window.GestureEvent = class extends UIEvent {}; }")
    touch("touchStart")
    expect(tip).to_be_visible()
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == ""
    expect(tip).to_be_visible()
    put_away()
    page.evaluate("() => { delete window.GestureEvent; }")

    touch("touchStart")
    page.wait_for_timeout(700)
    touch("touchEnd")
    page.wait_for_function("location.hash === '#far'")
    expect(tip).to_be_hidden()


# Where the preview stands against `id`'s box, and whether a press at that box's centre
# reaches it.
AGAINST = """(id) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  const el = document.getElementById(id);
  const box = el.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  return {left: Math.round(tip.left), top: Math.round(tip.top),
    bottom: Math.round(tip.bottom), window: innerHeight,
    meets: box.left < tip.right && tip.left < box.right && box.top < tip.bottom
      && tip.top < box.bottom,
    reached: document.elementFromPoint(x, y) === el};
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_preview_takes_its_place_again_as_what_holds_it_changes(
    engine, request, serve
):
    """Where a standing preview stands is decided again whenever what it was decided
    from changes, its own place the first tried: words that grow over a neighbour leave
    it where it stands, under the user's aim, held to the room that clears the
    neighbour, its last line ending in an ellipsis, so the neighbour shows whole and a
    press reaches it, and the pointer can still cross onto the preview; a declared point
    that moves inside its element takes the preview with it, a box the element changes
    in place as well as a new one; and a scroll that carries its target to where its
    side no longer holds it puts it on a side that does."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Standing again", "<p>Words.</p>")),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => {
          const aim = document.createElement('button');
          aim.id = 'aim';
          aim.textContent = 'A';
          aim.style = 'position: fixed; left: 300px; top: 200px; width: 80px;'
            + ' height: 40px; padding: 0';
          aim.lfPreview = () => ({name: 'Preview words'});
          const next = document.createElement('button');
          next.id = 'next';
          next.textContent = 'Neighbour';
          next.style = 'position: fixed; left: 310px; top: 285px; width: 90px;'
            + ' height: 30px; padding: 0';
          window.pressed = 0;
          next.onclick = () => window.pressed++;
          document.body.append(aim, next);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#aim").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Preview words")
    short = page.evaluate(AGAINST, "next")
    assert not short["meets"], short
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          const aim = document.getElementById('aim');
          aim.lfPreview = () => ({name: 'Preview words', detail: [1, 2, 3, 4]
            .map((n) => `Additional detail on line ${n}`)});
          previewChanged(aim);
        }"""
    )
    expect(tip.locator(".lf-preview-detail")).to_have_count(4)
    rendered(page)
    grown = page.evaluate(AGAINST, "next")
    assert grown["top"] == short["top"], grown
    assert not grown["meets"] and grown["reached"], grown
    assert tip.locator("[data-lf-clamp], [data-lf-cut]").count() == 1
    held = tip.bounding_box()
    page.mouse.move(held["x"] + 20, held["y"] + 8, steps=4)
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    box = page.locator("#next").bounding_box()
    page.mouse.click(box["x"] + 45, box["y"] + 15)
    assert page.evaluate("window.pressed") == 1

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          for (const id of ['aim', 'next']) document.getElementById(id).remove();
          const chart = document.createElement('div');
          chart.id = 'chart';
          chart.style = 'position: fixed; left: 300px; top: 150px; width: 600px;'
            + ' height: 300px';
          chart.tabIndex = 0;
          window.pointX = 320;
          // The chart keeps one box for its point and changes it in place.
          const at = {left: 320, right: 330, top: 250, bottom: 260};
          chart.lfPreview = () => ({name: 'Point value', at});
          // A key the chart takes redraws it with its point moved and the same words.
          chart.addEventListener('keydown', (event) => {
            if (event.key !== 'F10') return;
            window.pointX = 700;
            Object.assign(at, {left: 700, right: 710});
            previewChanged(chart);
          });
          const toChart = document.createElement('button');
          toChart.id = 'to-chart';
          toChart.textContent = 'To the chart';
          document.body.append(toChart, chart);
        }"""
    )
    page.locator("#to-chart").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Point value")
    assert abs(page.evaluate(AGAINST, "chart")["left"] - 320) <= 1
    page.keyboard.press("F10")
    page.wait_for_function("window.pointX === 700")
    rendered(page)
    assert abs(page.evaluate(AGAINST, "chart")["left"] - 700) <= 1, "it stayed behind"

    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.set_viewport_size({"width": 900, "height": 400})
    page.evaluate(
        """() => {
          for (const id of ['chart', 'to-chart']) document.getElementById(id).remove();
          const aim = document.createElement('button');
          aim.id = 'held';
          aim.textContent = 'Held';
          const scroller = document.createElement('div');
          scroller.id = 'scroller';
          scroller.style = 'position: fixed; left: 200px; top: 0; width: 500px;'
            + ' height: 380px; overflow: auto';
          const inner = document.createElement('div');
          inner.style = 'padding-top: 250px; height: 800px';
          const before = document.createElement('button');
          before.id = 'before';
          before.textContent = 'Before';
          inner.append(before, aim);
          scroller.append(inner);
          document.body.append(scroller);
          aim.style = 'width: 80px; height: 40px; padding: 0';
          aim.lfPreview = () => ({name: 'Scrolled value',
            detail: Array.from({length: 7}, (_, n) => `Detail ${n}`)});
        }"""
    )
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Scrolled value")
    page.locator("#scroller").evaluate("el => { el.scrollTop = 200; }")
    rendered(page)
    scrolled = page.evaluate(AGAINST, "held")
    assert scrolled["top"] >= 0 and scrolled["bottom"] <= scrolled["window"], scrolled


def test_a_pinch_zoomed_window_holds_its_preview_in_what_it_shows(browser, serve):
    """Zoomed in by a pinch, the window shows part of the page, and a preview stands
    whole inside that part. Chromium alone: Playwright pinches no other engine."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Pinched",
                '<p><button id="before">Before</button></p>'
                '<button id="aim" style="position: absolute; left: 500px; top: 200px"'
                ' aria-label="A control whose name runs on long enough to need room">'
                "⚙</button>",
            )
        ),
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
    page.wait_for_function("visualViewport.scale === 2")
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("A control whose name")
    rendered(page)
    held = page.evaluate(
        """() => {
          const tip = document.getElementById('lf-preview').getBoundingClientRect();
          const v = visualViewport;
          return {left: tip.left - v.offsetLeft, right: v.offsetLeft + v.width - tip.right,
            top: tip.top - v.offsetTop, bottom: v.offsetTop + v.height - tip.bottom};
        }"""
    )
    assert min(held.values()) >= 0, held


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_name_longer_than_its_room_ends_in_an_ellipsis(engine, request, serve):
    """A name that wraps to more lines than the room holds shows the lines that fit,
    the last ending in an ellipsis, as a long title one span holds: none is cut through
    by the face's edge. The room alone decides it, so a window grown to hold the whole
    name shows it whole, standing or shown again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Long name",
                '<p><button id="before">Before</button></p>'
                '<p><button id="aim">Aim</button></p>',
            )
        ),
    )
    page.evaluate(
        """() => { document.getElementById('aim').lfPreview = () => ({name:
          Array.from({length: 80}, (_, n) => `word${n}`).join(' ')}); }"""
    )
    page.set_viewport_size({"width": 900, "height": 180})
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("word0")
    rendered(page)
    held = page.evaluate(
        """() => {
          const face = document.querySelector('#lf-preview .lf-preview-face');
          const word = face.querySelector('.lf-preview-word');
          return {face: face.getBoundingClientRect().bottom,
            word: word.getBoundingClientRect().bottom,
            clamp: getComputedStyle(word).webkitLineClamp, window: innerHeight};
        }"""
    )
    assert held["word"] <= held["face"] + 0.5, held
    assert held["clamp"] not in ("none", ""), held
    page.set_viewport_size({"width": 900, "height": 800})
    rendered(page)
    clamped = "() => document.querySelectorAll('#lf-preview [data-lf-clamp]').length"
    assert page.evaluate(clamped) == 0, "the clamp stayed as the window grew"
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("word79")
    rendered(page)
    assert page.evaluate(clamped) == 0, "the clamp stayed as it showed again"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_widget_s_new_aim_reads_again_whichever_child_holds_focus(
    engine, request, serve
):
    """A widget that declares its preview while a control inside it holds focus says
    the user aimed at something new (`previewChanged` with `aim`): the preview reads
    the widget again, and after Escape put it away the next aim shows it again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Owner",
                '<div id="host"><button id="inner">Item one</button></div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          window.lfApi = await window.__lfWidgetApi();
          window.label = 'First item detail';
          document.getElementById('host').lfPreview = () => ({name: window.label});
        }"""
    )
    tip = page.locator(PREVIEW)
    aim = """(words) => {
      window.label = words;
      window.lfApi.previewChanged(document.getElementById('host'), {aim: true});
    }"""
    page.keyboard.press("Shift")
    page.evaluate(
        "() => window.lfApi.focusDestination(document.getElementById('inner'), 'move')"
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("First item detail")
    page.evaluate(aim, "Second item detail")
    expect(tip.locator(".lf-preview-word")).to_have_text("Second item detail")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate(aim, "Third item detail")
    expect(tip).to_be_visible()
    expect(tip.locator(".lf-preview-word")).to_have_text("Third item detail")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_focus_moved_into_a_dialog_already_open_previews(engine, request, serve):
    """A move into a dialog that already stands is the user's, as one beside it is, so
    the control it lands on previews; only a surface placing focus as it opens shows
    none, as one a widget opens through `openLayer` does."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Open dialog",
                '<button id="outside">Outside</button><div role="dialog" id="open"'
                ' aria-label="Standing"><button id="inside">I</button></div>'
                '<div role="dialog" id="opening" aria-label="Opening" hidden>'
                '<button id="first">F</button></div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          for (const id of ['outside', 'inside', 'first'])
            document.getElementById(id).lfPreview = () => ({name: `${id} detail`});
          // A key that moves the user to a place, as a command's walk does.
          const to = {F9: 'outside', F10: 'inside'};
          addEventListener('keydown', (event) => {
            if (event.key === 'F8') {
              // A widget opening its dialog, which places the user on its first control.
              event.preventDefault();
              const opening = document.getElementById('opening');
              api.openLayer(opening);
              opening.hidden = false;
              api.focusDestination(document.getElementById('first'), 'move');
              return;
            }
            if (!to[event.key]) return;
            event.preventDefault();
            api.focusDestination(document.getElementById(to[event.key]), 'move');
          }, true);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.keyboard.press("F9")
    expect(tip.locator(".lf-preview-word")).to_have_text("outside detail")
    page.keyboard.press("F10")
    expect(tip.locator(".lf-preview-word")).to_have_text("inside detail")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.keyboard.press("F8")
    expect(page.locator("#first")).to_be_focused()
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_aim_at_what_says_nothing_leaves_the_standing_preview(
    engine, request, serve
):
    """Only a new reading replaces a standing preview: an aim at an element that says
    nothing there leaves it standing, as plain text does. Keyboard focus reads one
    element while the pointer rests on another, which then says it changed and now says
    nothing, as a chart does as its point's ring comes off; then the pointer crosses
    that element where it says nothing, as empty space inside a chart."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Nothing to say",
                '<p><button id="before">Before</button></p>'
                '<p><span id="focused" tabindex="0">Focused</span></p>'
                '<div id="pointed" style="width: 320px; height: 120px">Pointed</div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          window.lfApi = await window.__lfWidgetApi();
          window.lfSays = true;
          document.getElementById('focused').lfPreview = () => ({name: 'Focus reads'});
          document.getElementById('pointed').lfPreview = () =>
            window.lfSays ? {name: 'Pointer reads'} : null;
        }"""
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    page.locator("#pointed").hover()
    expect(word).to_have_text("Pointer reads")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(word).to_have_text("Focus reads")
    page.evaluate(
        """() => {
          window.lfSays = false;
          window.lfApi.previewChanged(document.getElementById('pointed'));
        }"""
    )
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    expect(word).to_have_text("Focus reads")
    box = page.locator("#pointed").bounding_box()
    page.mouse.move(box["x"] + 300, box["y"] + 100, steps=6)
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    expect(word).to_have_text("Focus reads")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_window_resize_decides_once_where_a_preview_stands(engine, request, serve):
    """A resize of the window changes the window, the visible viewport and maybe the
    target's size at once, and the standing preview decides where it stands once for
    all of them."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Resized",
                '<p><button id="before">Before</button></p>'
                '<p><span id="aim" tabindex="0">A value</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          document.getElementById('aim').lfPreview = () => ({name: 'A value says'});
          // Each decision (preview.js, `stand`) measures the preview's width once; the
          // page's watches measure it too.
          const tip = document.getElementById('lf-preview');
          const measure = tip.getBoundingClientRect;
          window.lfDecisions = 0;
          tip.getBoundingClientRect = function () {
            const stack = new Error().stack ?? '';
            if (stack.includes('at stand (') || stack.includes('stand@'))
              window.lfDecisions += 1;
            return measure.call(this);
          };
        }"""
    )
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("A value says")
    rendered(page)
    page.evaluate("() => { window.lfDecisions = 0; }")
    page.set_viewport_size({"width": 1000, "height": 640})
    rendered(page)
    page.wait_for_timeout(200)
    assert page.evaluate("window.lfDecisions") == 1
