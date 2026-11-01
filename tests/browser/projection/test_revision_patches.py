"""What a live revision's patch changes: the markup and words it rewrote, the nodes,
widgets and editors it keeps, and the markup it releases."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import LIVE_V1, LIVE_V2, LIVE_V3, live_url
from render_harness import (
    EXAMPLE_PACKAGES,
    expect_obligations_answered,
    leaf_page,
    open_page,
    panel_menu,
    panel_settled,
    panel_view,
    round_trip,
    scroll_settled,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_revision_leaves_root_attributes_it_does_not_change_untouched(browser, serve):
    """Authored `html` and `body` attributes both revisions write stay where they are.

    A body class taken off and put back restyles the whole document, so a revision
    that changes only the page's words writes nothing to either root. An empty custom
    property reads back as "", and stays declared all the same."""
    empty = '<body class="live-second" data-live-body="second" style="--live-body: 2'
    page = open_page(
        browser, live_url(serve(LIVE_V2.replace(empty, f"{empty}; --live-empty: ")))
    )
    page.evaluate(
        """() => {
          window.__lfRootWrites = [];
          new MutationObserver((records) => {
            for (const r of records)
              if (!r.attributeName.startsWith("data-lf-"))
                window.__lfRootWrites.push(
                  `${r.target.localName} ${r.attributeName} ${r.oldValue}`,
                );
          }).observe(document.documentElement, { attributes: true, attributeOldValue: true });
        }"""
    )
    page.evaluate(
        """() => new MutationObserver((records) => {
          for (const r of records)
            if (["class", "style", "data-live-body"].includes(r.attributeName))
              window.__lfRootWrites.push(`body ${r.attributeName} ${r.oldValue}`);
        }).observe(document.body, { attributes: true, attributeOldValue: true })"""
    )
    (serve.page_dir / "index.html").write_text(
        LIVE_V2.replace(
            "<title>Live second</title>", "<title>Live again</title>"
        ).replace(empty, f"{empty}; --live-empty: ")
    )
    told(page)
    expect(page).to_have_title("Live again")
    assert page.evaluate("window.__lfRootWrites") == []
    assert page.evaluate("[...document.body.style].includes('--live-empty')")

    # A revision that newly declares an empty property puts it on.
    (serve.page_dir / "index.html").write_text(
        LIVE_V2.replace(
            "<title>Live second</title>", "<title>Live more</title>"
        ).replace(empty, f"{empty}; --live-empty: ; --live-added: ")
    )
    told(page)
    expect(page).to_have_title("Live more")
    assert page.evaluate("[...document.body.style].includes('--live-added')")


def test_a_revision_updates_body_siblings_and_keeps_the_users_header_editor(
    browser, serve
):
    """Header, nav and footer participate in the same revision as main, and keep the
    first Tab stop ahead of Leaf's chrome. The retained body and chrome keep the
    user's input, current location and runtime state."""
    first = leaf_page(
        "Sibling first", '<h1 id="title">Release</h1><p id="plan">Ship Monday.</p>'
    )
    first = first.replace(
        "<body>",
        '<body class="before"><header id="masthead"><label>Name <input id="name" value="Max"></label><nav id="routes"><a href="#plan">Plan</a></nav></header>',
    )
    first = first.replace(
        "</body>",
        '<footer id="site-footer"><p id="site-note">First footer.</p></footer></body>',
    )
    page = open_page(browser, live_url(serve(first)))
    expect(page.get_by_role("banner")).to_have_count(1)
    expect(page.get_by_role("contentinfo")).to_have_count(1)
    page.keyboard.press("Tab")
    expect(page.locator("#name")).to_be_focused()
    page.locator("#name").fill("Maximilian")
    page.evaluate("window.heldChrome = document.querySelector(':root > .lf-chrome')")
    origin = page.evaluate("performance.timeOrigin")
    second = (
        first.replace("Sibling first", "Sibling second")
        .replace('class="before"', 'class="after"')
        .replace("Ship Monday.", "Ship Tuesday.")
        .replace("First footer.", "Revised footer.")
        .replace(">Plan</a>", ">Release plan</a>")
    )
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Sibling second")
    expect(page.locator("#site-note")).to_have_text("Revised footer.")
    expect(page.locator("#routes a")).to_have_text("Release plan")
    expect(page.locator("#plan")).to_have_text("Ship Tuesday.")
    expect(page.locator("#name")).to_have_value("Maximilian")
    expect(page.locator("#name")).to_be_focused()
    expect(page.locator("body")).to_have_class("after")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    assert page.evaluate("performance.timeOrigin") == origin
    assert page.evaluate(
        "window.heldChrome === document.querySelector(':root > .lf-chrome')"
    )
    # Removal and insertion at the shared body boundary must leave the runtime intact.
    third = second.replace(
        '<footer id="site-footer"><p id="site-note">Revised footer.</p></footer>',
        '<aside id="next">Next release</aside>',
    ).replace("Sibling second", "Sibling third")
    (serve.page_dir / "index.html").write_text(third)
    told(page)
    expect(page).to_have_title("Sibling third")
    expect(page.locator("#site-footer")).to_have_count(0)
    expect(page.locator("#next")).to_have_text("Next release")
    assert page.evaluate(
        "window.heldChrome === document.querySelector(':root > .lf-chrome')"
    )


def test_a_revision_brings_its_page_layout_to_the_body(browser, serve):
    """The body's geometry follows the page's Layout across a live revision.

    A Layout's body rules read the Layout delivery repeats on the root, so a revision
    that drops the Layout hands the body back the browser's margin, and one that names
    it again takes the margin away."""
    margin = "getComputedStyle(document.body).marginTop"
    page = open_page(browser, live_url(serve(LIVE_V1)))
    assert page.evaluate(margin) == "0px"

    (serve.page_dir / "index.html").write_text(
        LIVE_V2.replace('<main class="layout-column">', "<main>")
    )
    told(page)
    expect(page).to_have_title("Live second")
    assert page.evaluate(margin) == "8px"

    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    expect(page).to_have_title("Live third")
    assert page.evaluate(margin) == "0px"


def test_a_revision_leaves_the_page_everything_it_did_not_write(browser, serve):
    """A patch applies the author's difference, not the difference from the page.

    Everything the browser, the runtime, a user, or a page module has done to a page
    since it loaded makes the page differ from any source, so a patch that reconciled
    the live tree against the arriving revision would take all of it back. Four owners,
    none of them the author, on one page: the user's open disclosure, the tokenizer's
    spans in a code block, a tab stop `focus.js` lends to land the keyboard somewhere,
    and what a page module built inside an authored container. The revision rewrites one
    paragraph and mentions none of them.

    The same revision rewrites two more paragraphs. One a page module relocated into
    its own box, which is the module's to do: the words change where it stands, the
    node is the same, and no second copy arrives where the source wrote it. Above the
    other it inserts a paragraph, the one shape the gap cannot decide: both are
    paragraphs, neither carries a name, and the words that would have paired them are
    the words that changed. The user's node survives either way, and the page is whole
    and in order whichever way the diff falls.
    """
    body = """
<h1 id="ow-title">Owners</h1>
<details id="ow-details"><summary>Evidence</summary><p>The measured run.</p></details>
<pre id="ow-code"><code class="language-python">def run(value):
    return value + 1
</code></pre>
<div id="ow-built"></div>
<p id="ow-land">A paragraph the keyboard can land on.</p>
<p id="ow-edited">The cutover has not started.</p>
<div id="mv-box"></div>
<p id="mv-moved">The move has not started.</p>
<p id="mv-kept">A paragraph that stays where it was written.</p>
<section id="tw"><p>The twins have not started.</p></section>
"""
    module = (
        '<script type="module">'
        "document.getElementById('ow-built')"
        ".append(Object.assign(document.createElement('span'),"
        " {id: 'ow-made', textContent: 'built by the page'}));"
        "document.getElementById('mv-box')"
        ".append(document.getElementById('mv-moved'));"
        "</script>"
    )
    first = leaf_page("Owners first", body, head=module)
    second = (
        first.replace("Owners first", "Owners second")
        .replace(
            "The cutover has not started.",
            "The cutover finished on the second attempt.",
        )
        .replace(
            "The move has not started.", "The move finished on the second attempt."
        )
        .replace(
            "<p>The twins have not started.</p>",
            "<p>A finding above it.</p><p>The twins finished on the second attempt.</p>",
        )
    )
    page = open_page(browser, live_url(serve(first)))
    expect(page.locator("#ow-made")).to_have_text("built by the page")
    expect(page.locator("#mv-box > #mv-moved")).to_have_count(1)
    page.evaluate(
        """() => {
          window.__mvMoved = document.getElementById('mv-moved');
          const paragraph = document.querySelector('#tw p');
          window.__twParagraph = paragraph;
          window.__twNode = paragraph.firstChild;
        }"""
    )
    page.locator("#ow-details > summary").click()
    expect(page.locator("#ow-details")).to_have_attribute("open", "")
    # The runtime lends a tab stop to land the keyboard on a paragraph. Taking that
    # attribute back is taking the focus with it.
    page.locator("#ow-land").evaluate(
        "el => { el.tabIndex = -1; el.focus({preventScroll: true}); }"
    )
    held = page.evaluate(
        """() => ({
          spans: document.querySelectorAll('#ow-code code span').length,
          made: document.getElementById('ow-made'),
        })"""
    )
    assert held["spans"] > 1, "the code block was never highlighted"
    page.evaluate(
        "() => { window.__owFirstSpan = document.querySelector('#ow-code code span'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Owners second")
    expect(page.locator("#ow-edited")).to_have_text(
        "The cutover finished on the second attempt."
    )
    kept = page.evaluate(
        """() => ({
          open: document.getElementById('ow-details').hasAttribute('open'),
          spans: document.querySelectorAll('#ow-code code span').length,
          sameSpan:
            window.__owFirstSpan === document.querySelector('#ow-code code span'),
          made: Boolean(document.getElementById('ow-made')),
          landing: document.getElementById('ow-land').getAttribute('tabindex'),
          focused: document.activeElement === document.getElementById('ow-land'),
        })"""
    )
    assert kept == {
        "open": True,
        "spans": held["spans"],
        "sameSpan": True,
        "made": True,
        "landing": "-1",
        "focused": True,
    }, f"the revision took back what its author never wrote: {kept}"
    rewritten = page.evaluate(
        """() => {
          const paragraphs = [...document.querySelectorAll('#tw p')];
          return {
            moved: document.getElementById('mv-moved').textContent,
            sameNode: window.__mvMoved === document.getElementById('mv-moved'),
            inBox: document.getElementById('mv-moved').parentElement.id,
            copies: document.querySelectorAll('#mv-moved').length,
            twins: paragraphs.map((p) => p.textContent),
            twinKept: paragraphs.includes(window.__twParagraph),
            twinConnected: window.__twNode.isConnected,
          };
        }"""
    )
    assert rewritten == {
        "moved": "The move finished on the second attempt.",
        "sameNode": True,
        "inBox": "mv-box",
        "copies": 1,
        "twins": ["A finding above it.", "The twins finished on the second attempt."],
        "twinKept": True,
        "twinConnected": True,
    }, f"the revision did not reach what it rewrote in place: {rewritten}"


def test_a_revision_keeps_a_recording_on_leaf_s_play_bar(browser, serve):
    """The runtime trades a video's `controls` for its own play bar before first paint
    (video-controls.js). A revision that leaves the video as written keeps the node and
    the bar, and hands the browser's controls back to nobody."""
    body = """
<p id="rv-edited">The recording is a draft.</p>
<video id="rv-video" controls width="320" height="180" aria-label="Test pattern"
  src="/media/2930ad3df7819c50.mp4"></video>
"""
    first = leaf_page("Recording first", body)
    second = first.replace("Recording first", "Recording second").replace(
        "is a draft.", "is final."
    )
    page = open_page(browser, live_url(serve(first)))
    page.evaluate("() => { window.__video = document.getElementById('rv-video'); }")
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page.locator("#rv-edited")).to_have_text("The recording is final.")
    state = page.evaluate(
        """() => {
          const video = document.getElementById('rv-video');
          return {
            same: video === window.__video,
            controls: video.hasAttribute('controls'),
            bars: document.querySelectorAll('.lf-video-controls').length,
          };
        }"""
    )
    assert state == {"same": True, "controls": False, "bars": 1}, state


def test_a_revision_that_moves_the_block_the_user_types_in_keeps_them_there(
    browser, serve
):
    """A revision that reorders siblings moves the element the user is typing in.

    The patch keeps that element, so the carry leaves it alone. Native placement retains
    the browser's own state across the move: they stay in the box, caret included.
    """
    first = leaf_page(
        "Moved first",
        """
<h1 id="mv-title">Moved</h1>
<p id="mv-intro">The steps, in the order they ran.</p>
<p id="mv-late">The cutover ran second.</p>
<p id="mv-note"><label>Note <input id="mv-input" type="text"></label></p>
""",
    )
    late = '<p id="mv-late">The cutover ran second.</p>\n'
    second = (
        first.replace("Moved first", "Moved second")
        .replace(late, "")
        .replace("</label></p>\n", "</label></p>\n" + late)
    )
    assert second.index("mv-note") < second.index("mv-late")
    page = open_page(browser, live_url(serve(first)))
    box = page.locator("#mv-input")
    box.fill("needs a rollback")
    box.evaluate("input => input.setSelectionRange(6, 9, 'backward')")
    page.evaluate("() => { window.__mvInput = document.getElementById('mv-input'); }")

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Moved second")
    kept = page.evaluate(
        """() => {
          const input = document.getElementById('mv-input');
          return {
            order: [...document.querySelectorAll('main > p')].map((p) => p.id),
            same: input === window.__mvInput,
            focused: document.activeElement === input,
            caret: [input.selectionStart, input.selectionEnd, input.selectionDirection],
          };
        }"""
    )
    assert kept == {
        "order": ["mv-intro", "mv-note", "mv-late"],
        "same": True,
        "focused": True,
        "caret": [6, 9, "backward"],
    }, f"the revision's move took the user out of their box: {kept}"


def test_a_revision_reorders_a_live_sample_without_replacing_its_document(
    browser, serve
):
    """Moving a retained sample keeps its child document and focused unsent editor.

    A removal and reinsertion keeps the iframe element but reloads its document.
    Draft persistence can recover the words while still dropping the child's focus,
    so identity, words, and focus together establish that the child stayed live.
    """
    first = leaf_page(
        "Sample first",
        """
<h1 id="sample-title">Live sample revision</h1>
<p id="sample-before">This paragraph comes first.</p>
<lf-sample id="sample-held" label="Live draft" window>
  <template id="sample-source" data-sample>
    <h1>Practice draft</h1>
    <lf-draft id="sample-draft"><pre>Authored sample words.</pre></lf-draft>
  </template>
</lf-sample>
""",
    )
    paragraph = '<p id="sample-before">This paragraph comes first.</p>\n'
    second = (
        first.replace("Sample first", "Sample second")
        .replace(paragraph, "")
        .replace("</lf-sample>\n", "</lf-sample>\n" + paragraph)
    )
    page = open_page(browser, live_url(serve(first)))
    sample = page.locator("#sample-held")
    expect(sample.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    frame = sample.locator("iframe")
    frame.evaluate("frame => window.heldSampleDocument = frame.contentDocument")
    child = page.frame_locator("#sample-held iframe")
    child.locator(".lf-draft-body").click()
    editor = child.locator("#sample-draft leaf-text")
    write(editor, "Unsent sample words.")
    expect(editor).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Sample second")
    expect(page.locator("#sample-held + #sample-before")).to_be_attached()
    assert frame.evaluate(
        "frame => frame.contentDocument === window.heldSampleDocument"
    ), "the revision's retained sample move replaced its child document"
    expect(editor).to_have_js_property("value", "Unsent sample words.")
    expect(editor).to_be_focused()


def test_a_prose_revision_takes_only_the_words_it_rewrote(browser, serve):
    """The paragraph a revision rewrote is the only thing the user gives up.

    A native selection and the element a page was handed belong to nodes rather than
    markup. The selection still reads what it read over the same text node, the
    element is still the element, and the picker says the page moved. Focus follows
    the user's route through the page. An unrelated rewrite arrives automatically
    because the selected passage's complete authored scope remains unchanged.
    """
    first = leaf_page(
        "Prose first",
        """
<h1 id="pr-title">Prose</h1>
<p id="pr-kept">The account the user is halfway through, held across the revision.</p>
<p id="pr-edited">The cutover has not started.</p>
<button id="pr-control" type="button">Inspect</button>
""",
    )
    second = first.replace("Prose first", "Prose second").replace(
        "The cutover has not started.",
        "The cutover finished on the second attempt.",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#pr-control").focus()
    held = page.evaluate(
        """() => {
          const node = document.getElementById('pr-kept').firstChild;
          const range = document.createRange();
          range.setStart(node, 4);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__prKept = document.getElementById('pr-kept');
          window.__prNode = node;
          return selection.toString();
        }"""
    )
    assert held == "account", f"the selection did not stand where it was put: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Prose second")
    expect(page.locator("#pr-edited")).to_have_text(
        "The cutover finished on the second attempt."
    )
    kept = page.evaluate(
        """() => ({
          selection: getSelection().toString(),
          sameNode: getSelection().anchorNode === window.__prNode,
          sameElement: window.__prKept === document.getElementById('pr-kept'),
        })"""
    )
    assert kept == {
        "selection": "account",
        "sameNode": True,
        "sameElement": True,
    }, f"the revision took something the user was holding: {kept}"
    # The retained selection still names a commentable passage after the revision.
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("account")
    expect(
        panel_menu(page, "versions").locator(".lf-fp-version[data-current]")
    ).to_contain_text("Current · Draft after v1")


def test_a_revision_reaches_markup_wherever_its_source_holds_it(browser, serve):
    """A patch reads the source text, whitespace and all, and reaches markup wherever
    the source holds it, while what the revision never touched keeps its node. Six
    independent sections on one page, each revised or left alone by the same revision:

    - A template's tree is its content fragment, not its children. `childNodes` is
      empty on a template however much markup it holds, so a patch that read the
      element alone left every template frozen at the revision it arrived in —
      silently, because the element is there and its attributes even keep up.
    - A template written one line to a line holds a whitespace text node between every
      pair of lines and around both ends. Those nodes all read alike and outnumber the
      lines; one of them taking a line's pairing would put the rewrite in the wrong line
      or rebuild the fragment whole.
    - An unnamed widget is as much the user's as a named one. Unchanged authored
      markup keeps its node and whatever the user had open in it.
    - A widget that arrives alone inside an exhibit is told the parent it will stand
      under, so it arrives quoted, its actions closed, rather than open to a decision
      against material the page declares as evidence.
    - An authored class written over two lines patches, since source text is the
      patch's input.
    - Delivery writes each revision's root into every media address, so the same picture
      is spelled differently in two revisions that never touched it. The page keeps the
      address it has, still served because revisions are immutable, and the picture is
      not fetched again.
    """
    first = leaf_page(
        "Patched first",
        '<h1 id="pt-title">Patched</h1>\n'
        '<template id="tm-held" data-sample>'
        '<p class="tm-line">The first account.</p></template>\n'
        '<template id="tl-held" data-sample>\n'
        '  <p class="tl-line">The first line.</p>\n'
        '  <p class="tl-line">The <lf-gloss tip="held inside">second</lf-gloss>'
        " line.</p>\n"
        '  <p class="tl-line">The third line.</p>\n'
        "</template>\n"
        '<p id="tl-after">A <lf-gloss tip="after the template">term</lf-gloss> the'
        " template does not hold.</p>\n"
        '<p id="nm-kept">A <lf-gloss tip="the cutover of the store">cutover</lf-gloss>'
        " the user is asking about.</p>\n"
        '<p id="nm-edited">The store has not moved.</p>\n'
        '<lf-sample id="qt-spec" label="an inert pick">\n'
        '  <lf-options id="qt-opts" choose>\n'
        '    <lf-option id="qt-a">Alpha</lf-option>\n'
        '    <lf-option id="qt-b">Beta</lf-option>\n'
        "  </lf-options>\n"
        "</lf-sample>\n"
        '<p id="cs-note" class="note\n    aside">The cutover has not started.</p>\n'
        '<img id="md-shot" src="/media/051bee487bfb5d13.png" alt="a shot">',
    )
    second = (
        first.replace("Patched first", "Patched second")
        .replace("The first account.", "The second account, rewritten.")
        .replace("second</lf-gloss> line.", "second</lf-gloss> line, rewritten.")
        .replace("The store has not moved.", "The store moved.")
        .replace(">Beta<", ">Beta, rewritten<")
        .replace(
            "The cutover has not started.",
            "The cutover finished on the second attempt.",
        )
    )
    page = open_page(browser, live_url(serve(first)))
    template = "() => document.getElementById('tm-held').content.textContent"
    assert page.evaluate(template) == "The first account."
    quoted = (
        "async () => { const api = await window.__lfWidgetApi();"
        " const reading = api.widgetController(document.getElementById('qt-opts')).read();"
        " return { choose: reading.actions.choose.available,"
        " label: document.getElementById('qt-b').textContent.trim() }; }"
    )
    assert page.evaluate(quoted) == {"choose": False, "label": "Beta"}
    expect(page.locator("lf-gloss")).to_have_count(2)
    src = page.evaluate(
        """() => {
          window.__tlLines =
            [...document.getElementById('tl-held').content.querySelectorAll('p')];
          window.__tlAfter = document.querySelector('#tl-after > lf-gloss');
          window.__nmGloss = document.querySelector('#nm-kept > lf-gloss');
          window.__nmGloss.dataset.userHeld = 'open';
          const shot = document.getElementById('md-shot');
          window.__mdLoads = 0;
          shot.addEventListener('load', () => { window.__mdLoads += 1; });
          return shot.getAttribute('src');
        }"""
    )
    assert page.evaluate("() => window.__tlLines.length") == 3

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Patched second")
    expect(page.locator("#qt-b")).to_contain_text("Beta, rewritten")
    expect(page.locator("#cs-note")).to_have_text(
        "The cutover finished on the second attempt."
    )
    assert page.evaluate(template) == "The second account, rewritten.", (
        "the revision did not reach the markup inside the template"
    )
    kept = page.evaluate(
        """() => {
          const content = document.getElementById('tl-held').content;
          const lines = [...content.querySelectorAll('p')];
          return {
            words: lines.map((line) => line.textContent),
            kept: lines.map((line, at) => line === window.__tlLines[at]),
            nodes: content.childNodes.length,
            // The unnamed widget after the template is the second of its tag only
            // when the one held inside the template counts; keyed one short, its
            // digest names the wrong widget and the revision rebuilds it.
            afterKept:
              window.__tlAfter === document.querySelector('#tl-after > lf-gloss'),
            unnamedKept: window.__nmGloss === document.querySelector('#nm-kept > lf-gloss'),
            unnamedHeld: document.querySelector('#nm-kept > lf-gloss')?.dataset.userHeld,
            unnamedEdited: document.getElementById('nm-edited').textContent,
            classes: [...document.getElementById('cs-note').classList].sort(),
            src: document.getElementById('md-shot').getAttribute('src'),
            loads: window.__mdLoads,
          };
        }"""
    )
    assert kept == {
        "words": [
            "The first line.",
            "The second line, rewritten.",
            "The third line.",
        ],
        "kept": [True, True, True],
        "nodes": 7,
        "afterKept": True,
        "unnamedKept": True,
        "unnamedHeld": "open",
        "unnamedEdited": "The store moved.",
        "classes": ["aside", "note"],
        "src": src,
        "loads": 0,
    }, f"the revision missed what it rewrote or took what it left alone: {kept}"
    assert page.evaluate(quoted) == {
        "choose": False,
        "label": "Beta, rewritten",
    }, "the rewritten widget arrived unquoted"


def test_a_word_the_revision_adds_to_a_surviving_element_is_said(
    browser, serve, declared_reading_package
):
    """A newly authored label is readable and pointable on a surviving node."""
    first = leaf_page(
        "Said first",
        '<h1 id="sd-title">Said</h1>'
        '<lf-reading id="sd-reading"><p>Checks complete.</p></lf-reading>',
    )
    second = first.replace("Said first", "Said second").replace(
        'id="sd-reading"', 'id="sd-reading" label="Release checks"'
    )
    page = open_page(
        browser,
        live_url(serve(first, packages=(*EXAMPLE_PACKAGES, declared_reading_package))),
    )
    page.evaluate("window.__sample = document.getElementById('sd-reading')")

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Said second")
    expect(page.locator('#sd-reading [data-lf-said="label"]')).to_have_text(
        "Release checks"
    )
    assert page.evaluate("window.__sample === document.getElementById('sd-reading')")


def test_another_kind_of_sibling_above_an_edited_paragraph_keeps_the_user_on_it(
    browser, serve
):
    """The gap between pinned siblings is diffed, not walked in step.

    A stretch the revision edited also holds whatever it inserted, and a cursor meets an
    insertion in the way that costs the user their node: a heading above the paragraph
    they are reading is nothing the cursor can pair with, so it spends the cursor, and
    the paragraph is left with no partner and removed. Nothing is pinned here — the
    revision rewrote the only paragraph in the gap — so the whole answer comes from the
    gap's own diff.
    """
    first = leaf_page(
        "Kinds first",
        "<h1 id='kd-title'>Kinds</h1>\n<p>The cutover has not started.</p>",
    )
    second = first.replace("Kinds first", "Kinds second").replace(
        "<p>The cutover has not started.</p>",
        "<h2>Progress</h2>\n<p>The cutover finished on the second attempt.</p>",
    )
    page = open_page(browser, live_url(serve(first)))
    held = page.evaluate(
        """() => {
          const node = document.querySelector('main p').firstChild;
          const range = document.createRange();
          range.setStart(node, 4);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__kdNode = node;
          window.__kdParagraph = node.parentElement;
          return selection.toString();
        }"""
    )
    assert held == "cutover", f"the selection did not land on the word: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Kinds first")
    page.evaluate("() => { window.__kdFocus = document.activeElement; }")
    page.locator("button.lf-fp-row-notice-press").evaluate("el => el.click()")
    expect(page).to_have_title("Kinds second")

    expect(page.locator("main h2")).to_have_text("Progress")
    kept = page.evaluate(
        """() => ({
          words: document.querySelector('main p').textContent,
          sameParagraph: window.__kdParagraph === document.querySelector('main p'),
          sameNode: getSelection().anchorNode === window.__kdNode,
          selection: getSelection().toString(),
        })"""
    )
    assert kept == {
        "words": "The cutover finished on the second attempt.",
        "sameParagraph": True,
        "sameNode": True,
        "selection": "cutover",
    }, f"the inserted heading took the user's paragraph with it: {kept}"


def test_a_paragraph_inserted_above_the_user_does_not_shift_the_ones_below(
    browser, serve
):
    """Unnamed siblings are matched by what they say, not by where they stand.

    Walking the two child lists in step is right until something is inserted, and then
    it is wrong in the way that costs a user most: every later paragraph pairs with
    its neighbour, so the one they are reading keeps its node while its words are
    overwritten with the next paragraph's, and the last paragraph goes for want of a
    partner. None of these paragraphs carries an id, which is the case a page of prose
    is made of.
    """
    body = "\n".join(
        f"<p>Paragraph {n}. " + "Settled words. " * 6 + "</p>" for n in range(1, 5)
    )
    first = leaf_page("Prose order first", f"<h1 id='po-title'>Order</h1>\n{body}")
    second = first.replace("Prose order first", "Prose order second").replace(
        "<p>Paragraph 1.",
        "<p>Paragraph 0. A finding the revision put above everything else.</p>\n"
        "<p>Paragraph 1.",
    )
    page = open_page(browser, live_url(serve(first)))
    held = page.evaluate(
        """() => {
          const second = [...document.querySelectorAll('main p')][1];
          const node = second.firstChild;
          const range = document.createRange();
          range.setStart(node, 0);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__poNode = node;
          window.__poParagraph = second;
          return selection.toString();
        }"""
    )
    assert held == "Paragraph 2", f"the selection did not land on paragraph 2: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Prose order first")
    page.evaluate("() => { window.__poFocus = document.activeElement; }")
    page.locator("button.lf-fp-row-notice-press").evaluate("el => el.click()")
    expect(page).to_have_title("Prose order second")

    kept = page.evaluate(
        """() => {
          const paragraphs = [...document.querySelectorAll('main p')];
          return {
            words: paragraphs.map((p) => p.textContent.trim().split('.')[0]),
            selection: getSelection().toString(),
            sameNode: getSelection().anchorNode === window.__poNode,
            sameParagraph: window.__poParagraph === paragraphs[2],
          };
        }"""
    )
    assert kept == {
        "words": ["Paragraph 0", "Paragraph 1", "Paragraph 2", "Paragraph 3"]
        + ["Paragraph 4"],
        "selection": "Paragraph 2",
        "sameNode": True,
        "sameParagraph": True,
    }, f"the insertion shifted the paragraphs below it: {kept}"


def test_a_revision_replaces_the_widget_it_rewrote_and_keeps_the_one_it_did_not(
    browser, serve
):
    """A widget renders from its authored markup, so a rewritten one cannot be put right
    from outside it: it leaves, and its replacement arrives through capture and upgrade
    like any new element. The question beside it that the revision did not touch is the
    same element it always was, still holding the user's focus. Its image, SVG link,
    custom media attribute, inline CSS and scripts carry different delivery roots in
    each revision. The deferred classic script's line padding changes too. None changes
    authored identity, and delivery-owned presentation must not make it look rewritten."""
    first = leaf_page(
        "Widgets first",
        """
<lf-ask id="wd-store-ask"><h2>Which store?</h2>
<lf-options id="wd-store" choose>
  <lf-option id="wd-keep">Keep the store
  <img src="/page/held.svg" alt="Leaf" data-evidence="/media/051bee487bfb5d13.png">
  <svg width="16" height="16"><image width="16" height="16" xlink:href="/page/held.svg"></image></svg>
  <style>#wd-keep { --held-image: url("/page/held.svg"); }</style>
  <script type="module">if (false) import("/runtime/widget-api.js");</script>
  <script>if (false) import("/runtime/widget-api.js");</script>
</lf-option>
  <lf-option id="wd-drop">Drop the store</lf-option>
</lf-options></lf-ask>
<lf-ask id="wd-when-ask"><h2>Which schedule?</h2>
<lf-options id="wd-when" choose>
  <lf-option id="wd-now">Start now</lf-option>
  <lf-option id="wd-later">Start later</lf-option>
</lf-options></lf-ask>
""",
    )
    second = (
        first.replace("Widgets first", "Widgets second")
        .replace('<lf-ask id="wd-store-ask">', '\n<lf-ask id="wd-store-ask">')
        .replace(
            '<lf-option id="wd-later">Start later</lf-option>',
            '<lf-option id="wd-later">Start later</lf-option>\n'
            '  <lf-option id="wd-never">Do not start at all</lf-option>',
        )
        .replace(
            '<lf-ask id="wd-when-ask">',
            '<p><lf-tally id="arriving-tally" for="wd-when-ask" next></lf-tally></p>'
            '<lf-ask id="wd-when-ask">',
        )
    )
    page = open_page(
        browser,
        live_url(
            serve(
                first,
                page_files={
                    "held.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"></svg>'
                },
            )
        ),
    )
    mark = page.locator("#wd-keep .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    page.evaluate(
        "() => { window.__wdStore = document.getElementById('wd-store');"
        " window.__wdWhen = document.getElementById('wd-when'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Widgets second")
    expect(page.locator("#wd-never")).to_contain_text("Do not start at all")
    expect(page.locator("#wd-never .lf-pick")).to_have_count(1)
    expect(page.locator("#arriving-tally .lf-tally-words")).to_have_text(
        "1 left to answer"
    )
    assert page.evaluate("window.__wdWhen !== document.getElementById('wd-when')"), (
        "the rewritten question kept an element rendering the markup it replaced"
    )
    assert page.evaluate("window.__wdStore === document.getElementById('wd-store')"), (
        "the untouched question was replaced along with its neighbour"
    )
    expect(page.locator("#wd-keep .lf-pick")).to_be_focused()
    page.keyboard.press("1")
    expect(page.locator("#wd-keep")).to_have_attribute("chosen", "")
    page.locator("#wd-never .lf-pick").click()
    round_trip(page)
    expect(page.locator("#wd-never")).to_have_attribute("chosen", "")


def test_a_revision_inside_one_tab_keeps_the_tab_set_and_every_other_tab(
    browser, serve
):
    """A tab set's module builds its strip beside the panels and reads only their labels
    (`x-patch: members`), so a revision that rewrites a sentence in one tab edits that
    sentence: the tab set, the tab the user has open and the question in the other tab
    are the elements they were. A revision that adds a tab changes what the strip was
    built from, and the set is rebuilt with a tab for it."""

    def tabs(lede, extra=""):
        return f"""<lf-tabs id="tp-views">
  <lf-tab id="tp-plan" label="Plan"><p id="tp-lede">{lede}</p></lf-tab>
  <lf-tab id="tp-ask-tab" label="Ask">
    <lf-ask id="tp-store-ask"><h2>Which store?</h2>
    <lf-options id="tp-store" choose>
      <lf-option id="tp-keep">Keep the store</lf-option>
      <lf-option id="tp-drop">Drop the store</lf-option>
    </lf-options></lf-ask>
  </lf-tab>{extra}
</lf-tabs>"""

    first = leaf_page("Tabs first", tabs("Ship on Monday."))
    second = leaf_page("Tabs second", tabs("Ship on Tuesday."))
    third = leaf_page(
        "Tabs third",
        tabs(
            "Ship on Tuesday.",
            '\n  <lf-tab id="tp-notes" label="Notes"><p>Later.</p></lf-tab>',
        ),
    )
    page = open_page(browser, live_url(serve(first)))
    page.get_by_role("tab", name="Ask").click()
    expect(page.locator("#tp-ask-tab")).to_be_visible()
    page.evaluate(
        "() => { window.__tpTabs = document.getElementById('tp-views');"
        " window.__tpStore = document.getElementById('tp-store'); }"
    )

    stamp_page(serve.page_dir, second, "move the ship date")
    wait_for_revision(page, 2)
    expect(page.locator("#tp-lede")).to_have_text("Ship on Tuesday.")
    assert page.evaluate(
        "window.__tpTabs === document.getElementById('tp-views')"
        " && window.__tpStore === document.getElementById('tp-store')"
    ), "a sentence in one tab rebuilt the tab set"
    expect(page.locator("#tp-ask-tab")).to_be_visible()
    expect(page.get_by_role("tab")).to_have_count(2)

    stamp_page(serve.page_dir, third, "add a notes tab")
    wait_for_revision(page, 3)
    expect(page.get_by_role("tab")).to_have_count(3)
    page.get_by_role("tab", name="Notes").click()
    expect(page.locator("#tp-notes")).to_be_visible()


@pytest.mark.parametrize("departure", ["focused", "link", "selection"])
def test_a_revision_releases_the_served_markup_it_removes(browser, serve, departure):
    """Markup the page was served with leaves memory once a revision removes it. The
    served baseline's source copy routes each copied node to the live node it came
    from, so holding that copy past the revision that replaced it kept every served
    node alive for the rest of the session. A host painted before modules run is
    included, since the first-paint coordinator copies it separately. Neither the
    dropped focus, before another input, nor a fragment navigation step's history checkpoint
    may keep removed markup alive."""
    first = leaf_page(
        "Served",
        '<h1>Served</h1><section id="served"><h2>Served section</h2>'
        '<lf-activity id="served-feed"></lf-activity><p>Served words, and'
        ' <a id="served-link" href="#destination">a link in them</a>.</p>'
        '<p id="served-selection">A passage with a saved caret.</p></section>'
        '<div style="height:1600px"></div>'
        '<h2 id="destination">Destination</h2>'
        '<lf-ask id="question"><h2>A decision?</h2>'
        '<lf-options id="answer" choose><lf-option id="yes">Yes</lf-option>'
        "</lf-options></lf-ask>",
    )
    second = leaf_page("Revised", "<h1>Revised</h1><p>Revised words.</p>")
    page = open_page(browser, live_url(serve(first)))
    page.locator("#served-link").focus()
    page.keyboard.press("Shift")
    entries = page.evaluate("history.length")
    if departure == "link":
        page.locator("#served-link").click()
        expect(page.locator("#destination")).to_be_focused()
    elif departure == "selection":
        page.locator("#served-selection").click()
        assert (
            page.evaluate("getSelection().anchorNode.parentElement.id")
            == "served-selection"
        )
        page.keyboard.press("m")
        expect(page.locator("#question")).to_be_focused()
    if departure != "focused":
        assert page.evaluate("history.length") == entries + 1
        scroll_settled(page)
    rendered(page)
    page.evaluate(
        """() => {
          window.__held = ['served', 'served-feed', 'served-link', 'served-selection'].map(
            (id) => new WeakRef(document.getElementById(id)));
          // The control: a removed node nothing else holds, so a collection that
          // clears it has run.
          const control = document.createElement('p');
          document.body.append(control);
          control.remove();
          window.__control = new WeakRef(control);
        }"""
    )
    stamp_page(serve.page_dir, second, "remove the served section")
    wait_for_revision(page, 2)
    rendered(page)
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("HeapProfiler.collectGarbage")
    finally:
        cdp.detach()
    assert page.evaluate("() => window.__control.deref() === undefined")
    held = page.evaluate(
        "() => window.__held.map((ref) => ref.deref()?.id).filter(Boolean)"
    )
    assert held == [], f"the revision left the served {held} in memory"


@pytest.mark.parametrize("subject", ["diff", "selection"])
def test_a_live_revision_updates_the_closed_on_me_door(browser, serve, subject):
    """Unrelated questions arrive while an anchored comment keeps its native editor."""
    reading = (
        '<p id="reading">Work under discussion.</p>'
        if subject != "diff"
        else '<lf-diff id="reading"><pre>'
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-before()\n+after()\n</pre></lf-diff>"
    )
    first = leaf_page("Questions arriving", '<h1 id="h">Decisions</h1>' + reading)
    questions = "".join(
        f'<lf-ask id="question-{i}"><h2>Decision {i}?</h2>'
        f'<lf-options id="options-{i}" choose>'
        f'<lf-option id="yes-{i}">Yes</lf-option></lf-options></lf-ask>'
        for i in range(3)
    )
    second = first.replace(reading, questions + reading)
    page = open_page(browser, live_url(serve(first, packages=("diff",))))
    door = page.locator(".lf-fp-on-user")
    expect(door).to_have_attribute("aria-label", "On me")
    target = (
        page.locator("#reading")
        if subject != "diff"
        else page.locator("#reading [data-line]").last
    )
    if subject == "selection":
        target.click(click_count=3)
    else:
        target.click(modifiers=["Alt"])
    editor = page.locator(".lf-fab-input")
    if subject != "selection":
        expect(editor).to_be_focused()
    editor.evaluate("node => { window.heldComposer = node; }")

    # An empty but open composer was sufficient to hold the original report.
    (serve.page_dir / "index.html").write_text(second)
    expect(page.locator("lf-ask")).to_have_count(3)
    expect(door).to_have_attribute("aria-label", "On me: 3")
    if subject == "selection":
        assert (
            page.evaluate("getSelection().toString().trim()")
            == "Work under discussion."
        )
    else:
        expect(editor).to_be_focused()
    expect(editor).to_be_in_viewport()
    assert editor.evaluate("node => node === window.heldComposer")

    write(editor, "Keep this comment while questions change.")
    editor.evaluate("node => node.setSelectionRange(5, 9)")
    (serve.page_dir / "index.html").write_text(first)
    expect(page.locator("lf-ask")).to_have_count(0)
    expect(door).to_have_attribute("aria-label", "On me")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property(
        "value", "Keep this comment while questions change."
    )
    assert editor.evaluate("node => node === window.heldComposer")
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [5, 9]


def test_a_live_revision_holds_a_changed_comment_anchor_scope(browser, serve):
    """A retained paragraph is insufficient if the quote becomes ambiguous."""
    paragraph = "<p>Work under discussion.</p>"
    first = leaf_page(
        "Comment scope",
        '<h1 id="h">Decisions</h1><section id="subject">' + paragraph + "</section>",
    )
    second = first.replace("</section>", paragraph + "</section>").replace(
        "</main>",
        '<lf-ask id="question"><h2>Decision?</h2>'
        '<lf-options id="options" choose><lf-option id="yes">Yes</lf-option>'
        "</lf-options></lf-ask></main>",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#subject p").click(click_count=3)
    editor = page.locator(".lf-fab-input")
    write(editor, "This occurrence matters.")

    (serve.page_dir / "index.html").write_text(second)
    # The row offers the latest, without a press that would end the hold.
    expect(page.locator("button.lf-fp-row-notice-press")).to_be_enabled()
    expect(page.locator("#subject p")).to_have_count(1)
    expect(page.locator(".lf-fp-on-user")).to_have_attribute("aria-label", "On me")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "This occurrence matters.")

    editor.press("Escape")
    expect(page.locator("#subject p")).to_have_count(2)
    expect(page.locator(".lf-fp-on-user")).to_have_attribute("aria-label", "On me: 1")


def test_a_live_revision_preserves_an_unchanged_authored_editor(browser, serve):
    """The patch's native-node proof covers ordinary content controls too."""
    first = leaf_page(
        "Editor continuity",
        '<h1 id="h">Review</h1><label for="note">Review note</label>'
        '<textarea id="note"></textarea><p id="news">Original account.</p>',
    )
    page = open_page(browser, live_url(serve(first)))
    editor = page.locator("#note")
    write(editor, "Keep my words.")
    editor.evaluate("node => { window.heldNote = node; node.setSelectionRange(2, 7); }")
    second = first.replace("Original account.", "A revised account.")
    (serve.page_dir / "index.html").write_text(second)
    expect(page.locator("#news")).to_have_text("A revised account.")
    expect(editor).to_be_focused()
    expect(editor).to_have_value("Keep my words.")
    assert editor.evaluate("node => node === window.heldNote")
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [2, 7]

    third = second.replace('id="note"', 'id="note" placeholder="New instruction"')
    (serve.page_dir / "index.html").write_text(third)
    expect(page.locator("button.lf-fp-row-notice-press")).to_be_enabled()
    expect(editor).not_to_have_attribute("placeholder", "New instruction")
    expect(editor).to_have_value("Keep my words.")
    editor.press("Tab")
    expect(editor).to_have_attribute("placeholder", "New instruction")


def test_a_live_revision_reorders_the_page_and_obligation_inventory_together(
    browser, serve
):
    """Retained obligation descriptors follow the incoming document's order, and plain
    declared elements a revision removes leave the semantic document with their upgraded
    owner."""

    def question(identity, label):
        return f"""<lf-ask id="{identity}-ask"><h2>{label}?</h2>
  <lf-options id="{identity}-options" choose>
    <lf-option id="{identity}-yes">Yes</lf-option>
  </lf-options>
</lf-ask>"""

    first_question = question("first", "First")
    second_question = question("second", "Second")
    first = leaf_page(
        "Ask order first",
        f"<h1>Two questions</h1>{first_question}{second_question}"
        + question("gone", "Gone"),
    )
    second = leaf_page(
        "Ask order second",
        f"<h1>Two questions</h1>{second_question}{first_question}"
        "<p>The third decision is gone.</p>",
    )
    page = open_page(browser, live_url(serve(first)))
    expect_obligations_answered(page, "0/3")
    page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    cards = f"{panel_view('queue')} .lf-fp-on-item"
    expect(page.locator(cards)).to_have_count(3)

    def identities(selector, attribute):
        return page.locator(selector).evaluate_all(
            "(nodes, attribute) => nodes.map(node => node.getAttribute(attribute))",
            attribute,
        )

    def asked():
        return page.locator(cards).evaluate_all(
            "nodes => nodes.map(node => JSON.parse(node.dataset.key)[1])"
        )

    assert identities("main > lf-ask", "id") == ["first-ask", "second-ask", "gone-ask"]
    assert asked() == [
        "widget:first-options",
        "widget:second-options",
        "widget:gone-options",
    ]

    stamp_page(serve.page_dir, second, "reverse the questions, remove the third")
    wait_for_revision(page, 2)

    assert identities("main > lf-ask", "id") == ["second-ask", "first-ask"]
    # An open view keeps its cards where they stand while the user reads it; the
    # inventory's new order shows at the next opening.
    expect(page.locator(cards)).to_have_count(2)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    expect(page.locator(cards)).to_have_count(2)
    assert asked() == [
        "widget:second-options",
        "widget:first-options",
    ]
    descriptors = page.evaluate(
        """async () => {
          const {readApplication} = await window.__lfCheckApi();
          return [...readApplication().document.descriptors.keys()];
        }"""
    )
    assert not {"gone-ask", "gone-options", "gone-yes"} & set(descriptors)


def test_a_generated_shadow_editor_follows_an_arriving_live_version(browser, serve):
    """A retained generated shadow control follows unrelated authored changes."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))
    page.evaluate(
        """() => {
          const host = document.createElement('section');
          host.id = 'shadow-editor';
          const root = host.attachShadow({mode: 'open'});
          const box = document.createElement('textarea');
          box.dataset.lfOffer = '';
          root.append(box);
          document.querySelector('main').append(host);
          box.focus();
        }"""
    )

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")
    assert (
        page.evaluate(
            "() => document.querySelector('#shadow-editor').shadowRoot.activeElement?.tagName"
        )
        == "TEXTAREA"
    )
