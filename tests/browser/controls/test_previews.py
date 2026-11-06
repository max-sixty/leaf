"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import _publish
from render_harness import leaf_page, margins_laid_out, open_page, told

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
    """A finger held on a target reads its preview once the press is a long press, and
    letting go presses nothing, the browser's own click after the release included: a
    held link stays where it is, and its preview stands until the next touch, which puts
    it away. Where the browser says first that the press is long (`contextmenu`), the
    hold reads then and its menu stays shut. A press let go before the hold reads is a
    tap, which shows nothing and follows the link, its preview standing or not."""
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
        """() => {
          const go = document.getElementById('go');
          go.lfPreview = () => ({name: 'Where it goes'});
          window.lfHeld = [];
          for (const type of ['pointerdown', 'pointerup'])
            go.addEventListener(type, (event) => window.lfHeld.push(event.timeStamp));
        }"""
    )
    cdp = context.new_cdp_session(page)
    tip = page.locator(PREVIEW)
    box = page.locator("#go").bounding_box()
    point = {"x": box["x"] + 10, "y": box["y"] + box["height"] / 2}
    elsewhere = page.locator("#far").bounding_box()

    def touch(kind, at=point):
        cdp.send(
            "Input.dispatchTouchEvent",
            {"type": kind, "touchPoints": [at] if kind != "touchEnd" else []},
        )

    touch("touchStart")
    expect(tip.locator(".lf-preview-word")).to_have_text("Where it goes")
    expect(tip).to_have_attribute("data-lf-route", "hold")
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == "", "the held link was followed"
    expect(tip).to_be_visible()
    expect(page.locator("#go")).to_have_attribute("data-lf-held", "")
    touch("touchStart", {"x": elsewhere["x"] + 10, "y": elsewhere["y"] + 4})
    touch("touchEnd")
    expect(tip).to_be_hidden()

    touch("touchStart")
    menu = page.evaluate(
        """() => document.getElementById('go').dispatchEvent(new PointerEvent(
          'contextmenu', {bubbles: true, cancelable: true, composed: true,
                          pointerType: 'touch'}))"""
    )
    assert menu is False, "the platform's menu opened over the held preview"
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == ""
    expect(tip).to_be_visible()

    page.evaluate("window.lfHeld = []")
    touch("touchStart")
    page.wait_for_timeout(300)
    touch("touchEnd")
    page.wait_for_function("location.hash === '#far'")
    down, up = page.evaluate("window.lfHeld")
    assert up - down < 450, f"the machine held the finger {up - down:.0f} ms"
    expect(tip).to_be_hidden()
