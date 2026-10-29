"""The reader's place: Back and Forward, travel groups, reading landmarks, aligning the
current item, and restoring a remembered selection."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_layout import page_at_rest
from render_cases_navigation import CHIPS, DIFF_PAGE, _publish
from render_harness import (
    LONG_PAGE,
    PANEL,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
    panel_menu,
    panel_settled,
    panel_view,
    press_visible,
    resized,
    scroll_settled,
    select,
    selection_field,
    stamp_page,
    take_browser_errors,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_restoring_a_reading_start_paints_its_continuation_before_the_frame(
    browser, serve
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Restore reading",
                '<div id="reading" style="height:200px;overflow:auto">'
                '<div style="height:1200px">Reading to restore</div></div>',
            )
        ),
    )
    page.evaluate("""async () => {
      const api = await window.__lfWidgetApi();
      const host = document.querySelector('#reading');
      const region = {id:'reading', host, body:host};
      window.reading = {api, host, region, stop:api.registerReadingRegion(region)};
    }""")
    expect(page.locator("#reading")).to_have_attribute("data-lf-more-below", "")
    page.evaluate("""() => {
      const p = window.reading;
      p.place = p.api.capturePlace(p.region);
      p.host.scrollTop = p.host.scrollHeight;
    }""")
    expect(page.locator("#reading")).not_to_have_attribute("data-lf-more-below", "")
    # A resize restoration happens after this frame's native scroll delivery.
    # Read in its microtask checkpoint: waiting for a frame hides the stale cue.
    restored = page.evaluate("""() => new Promise(resolve => {
      const p = window.reading;
      let started = false;
      const observer = new ResizeObserver(() => {
        if (!started) {
          requestAnimationFrame(() => {started = true; p.host.style.height = '220px'});
          return;
        }
        p.api.restorePlace(p.place, p.region);
        queueMicrotask(() => {
          observer.disconnect();
          const result = {top:p.host.scrollTop,
            more:p.host.hasAttribute('data-lf-more-below')};
          p.stop();
          resolve(result);
        });
      });
      observer.observe(p.host);
    })""")
    assert restored == {"top": 0, "more": True}


# Authored controls distinguish resuming Tab at the reading from restarting at the top.
READING_CONTROLS_PAGE = LONG_PAGE.replace(
    '<h1 id="t">', '<button id="first-control">First control</button><h1 id="t">'
).replace(
    "<p id='p41'>",
    '<p id="p41"><button id="next-control">Next reading control</button>',
)


# Each route once and each reading region once.
@pytest.mark.parametrize(("nested", "route"), [(False, "Close"), (True, "Escape")])
def test_page_map_cancellation_returns_to_its_opener_without_moving_the_reading(
    browser, serve, route, nested
):
    content = (
        '<div style="height:900px"></div><button id="reading-control">Reading control</button>'
        '<div style="height:900px"></div>'
    )
    if nested:
        content = (
            f'<div id="reading" style="height:350px;overflow:auto">{content}</div>'
        )
    page = open_page(browser, serve(leaf_page("Map return", content)))
    page.locator("#reading-control").focus()
    page.locator("#reading-control").scroll_into_view_if_needed()
    reading = """() => ({page: document.scrollingElement.scrollTop,
      nested: document.querySelector('#reading')?.scrollTop ?? 0})"""
    before = page.evaluate(reading)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    if route == "Escape":
        page.keyboard.press("Escape")
    else:
        sheet.get_by_role("button", name="Close Page Map").click()
    expect(sheet).to_be_hidden()
    expect(page.locator("#reading-control")).to_be_focused()
    assert page.evaluate(reading) == before


@pytest.mark.parametrize("route", ["Escape", "Close"])
def test_page_map_cancellation_without_an_opener_keeps_the_scrolled_reading(
    browser, serve, route
):
    page = open_page(browser, serve(READING_CONTROLS_PAGE))
    page.evaluate("() => document.getElementById('p40').scrollIntoView()")
    page_at_rest(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    if route == "Escape":
        page.keyboard.press("Escape")
    else:
        sheet.get_by_role("button", name="Close Page Map").click()
    expect(sheet).to_be_hidden()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    page.keyboard.press("Tab")
    expect(page.locator("#next-control")).to_be_focused()


def test_history_returns_the_working_place_as_well_as_the_viewport(browser, serve):
    """Back and Forward restore the place commands read, not just its pixels."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Return to the source",
                """
<h1>Return to the source</h1>
<section id="source" style="min-height:900px">
  <h2>Source</h2><a id="reference" href="#destination">Read the destination</a>
</section>
<section id="middle" style="min-height:900px"><h2>Middle</h2></section>
<section id="destination" style="min-height:900px"><h2>Destination</h2></section>
""",
            )
        ),
    )
    # Following the reference is a real arrival, not a script assigning focus.
    page.locator("#reference").click()
    expect(page.locator("#destination")).to_be_focused()
    scroll_settled(page)
    page.go_back()
    expect(page.locator("#reference")).to_be_focused()
    page.wait_for_function("scrollY < 100")
    page.go_forward()
    expect(page.locator("#destination")).to_be_focused()
    page.go_back()
    expect(page.locator("#reference")).to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", "Comment on a · Read the destination"
    )


@pytest.mark.parametrize("close_source", [False, True])
def test_history_returns_only_a_visible_caret(browser, serve, close_source):
    """A caret in prose is a working place even when no element holds focus."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Return to prose",
                """
<h1>Return to prose</h1>
<details id="source-fold" open><summary>The source</summary>
<p id="source">Read this source passage before the question.</p></details>
<div style="height:1600px"></div>
<lf-ask id="question"><h2>Where should we build?</h2>
<lf-options id="places" choose><lf-option id="here">Here</lf-option>
<lf-option id="there">There</lf-option></lf-options></lf-ask>
""",
            )
        ),
    )
    page.locator("#source").click()
    before = page.evaluate("""() => {
      const s = getSelection();
      return {at: s.focusNode.parentElement.id, offset: s.focusOffset};
    }""")
    assert before["at"] == "source"
    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    if close_source:
        page.locator("#source-fold > summary").click()
    page.go_back()
    page.wait_for_function("document.activeElement === document.body")
    returned = page.evaluate("""() => {
      const s = getSelection();
      return s.focusNode && {at: s.focusNode.parentElement.id, offset: s.focusOffset};
    }""")
    assert returned == (None if close_source else before)


@pytest.mark.parametrize(
    ("route", "large", "focusable"),
    [("click", False, True), ("Tab", False, True), ("click", True, False)],
)
def test_a_new_reading_passage_ends_a_travel_group(
    browser, serve, route, large, focusable
):
    """Visible remnants of an old landing cannot swallow a deliberate reading move.
    Back returns the newly chosen passage; another Back reaches the original reading.
    Clicks on unfocusable words count too, independently of browser focus arrival."""
    stop = ' tabindex="0"' if focusable else ""
    elsewhere = f'<p id="elsewhere"{stop}>This independent paragraph has no thread.</p>'
    first = (
        '<section id="first"><p>The first discussion concerns the importer.</p>'
        f'<div style="height:1800px"></div>{elsewhere}</section>'
        if large
        else f'<p id="first">The first discussion concerns the importer.</p>{elsewhere}'
    )
    url = serve(
        leaf_page(
            "A fresh reading stop",
            "<h1>Reading before the conversations</h1>"
            '<p id="origin" tabindex="0">The reading before the thread navigation group.</p>'
            f'<div style="height:1800px"></div>{first}'
            '<div style="height:1800px"></div>'
            '<p id="second">The second discussion concerns the rollout.</p>'
            '<div style="height:900px"></div>',
        )
    )
    roots = [
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": target},
                "text": f"A question about {target}.",
            },
        )["id"]
        for target in ["first", "second"]
    ]
    page = open_page(browser, url)
    page.locator("#origin").click()
    entries = page.evaluate("history.length")
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-margin-preview [data-thread="{roots[0]}"]')
    ).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("history.length") == entries + 1

    if route == "Tab":
        # Return to reading without choosing a new passage, then take the browser's
        # own next stop, which is the independent paragraph after the first target.
        page.keyboard.press("g")
        page.keyboard.press("p")
        page.keyboard.press("Tab")
    else:
        page.locator("#elsewhere").click()
    if focusable:
        expect(page.locator("#elsewhere")).to_be_focused()
    else:
        page.wait_for_function(
            "() => getSelection().focusNode?.parentElement.closest('#elsewhere')"
        )
    scroll_settled(page)
    assert page.locator("#first").evaluate(
        "el => { const r=el.getBoundingClientRect(); return r.bottom > 60 && r.top < innerHeight-60; }"
    ), "the old landing must still be visible to expose accidental history grouping"
    chosen_top = page.evaluate("scrollY")
    page.keyboard.press("t")
    second = page.locator(f'.lf-margin-preview [data-thread="{roots[1]}"]')
    expect(second).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("history.length") == entries + 2

    if focusable:
        # Keep the card in its closing frame through Forward: a painted but inert
        # card is already put away, so history must return through its page target.
        page.locator(".lf-margin-preview").evaluate("""preview => {
          preview.addEventListener('transitionrun', event => {
            if (event.propertyName === 'opacity' && preview.inert)
              preview.getAnimations().forEach(animation => animation.pause());
          });
        }""")
    page.go_back()
    page.wait_for_function("top => Math.abs(scrollY-top) <= 2", arg=chosen_top)
    if focusable:
        expect(page.locator("#elsewhere")).to_be_focused()
    else:
        page.wait_for_function(
            "() => getSelection().focusNode?.parentElement.closest('#elsewhere')"
        )
    page.wait_for_function("navigation.transition === null")
    if focusable:
        page.wait_for_function("""() => {
          const preview = document.querySelector('.lf-margin-preview');
          return preview.inert && preview.getAnimations().some(a => a.playState === 'paused');
        }""")
    page.go_forward()
    page.wait_for_function("navigation.transition === null")
    # A margin card that has closed on Back returns through its source; one still
    # the current location returns focus to its card. Both are the second thread's working place.
    assert page.evaluate(
        "id => document.activeElement.id === 'second' || "
        "document.activeElement.closest('[data-thread]')?.dataset.thread === id",
        arg=roots[1],
    )
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    page.wait_for_function("top => Math.abs(scrollY-top) <= 2", arg=chosen_top)
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(page.locator("#origin")).to_be_focused()
    page.wait_for_function("scrollY < 100")


@pytest.mark.parametrize(
    "concealment",
    # One of each way words can be absent from what is drawn: not rendered (`hidden`
    # and a closed `details` are `display: none`'s case), rendered unseen, skipped
    # (`until-found` is `content-visibility`'s), and boxless.
    [
        "none",
        "display",
        "visibility",
        "opacity",
        "content",
        "contents",
    ],
)
def test_same_passage_and_controls_keep_a_mixed_travel_group(
    browser, serve, concealment
):
    """Reading choices have passage grain: touching the current words or operating
    controls does not turn consecutive thread/obligation travel into separate Back stops."""
    concealed = {
        "none": "",
        "hidden": "<div hidden><p>Concealed source background.</p></div>",
        "until-found": '<div hidden="until-found"><p>Concealed source background.</p></div>',
        "display": '<div style="display:none"><p>Concealed source background.</p></div>',
        "visibility": '<div style="visibility:hidden"><p>Concealed source background.</p></div>',
        "opacity": '<div style="opacity:0"><p>Concealed source background.</p></div>',
        "content": '<div style="content-visibility:hidden"><p>Concealed source background.</p></div>',
        "details": "<details><summary hidden>Background</summary><p>Concealed source background.</p></details>",
        "contents": "",
    }[concealment]
    style = ' style="display:contents"' if concealment == "contents" else ""
    url = serve(
        leaf_page(
            "One continuing navigation group",
            "<h1>One continuing navigation group</h1>"
            '<p id="origin" tabindex="0">The original reading place.</p>'
            '<div style="height:1800px"></div>'
            f'<section id="first">{concealed}'
            f'<p id="first-reading"{style}><span>The passage the first thread concerns.</span></p></section>'
            '<p><button id="reading-control">A nearby control</button></p>'
            '<div style="height:1800px"></div>'
            '<lf-ask id="second"><h2>Choose the next step</h2>'
            '<lf-options id="choice" choose><lf-option id="yes">Yes</lf-option>'
            '<lf-option id="no">No</lf-option></lf-options></lf-ask>'
            '<div style="height:900px"></div>',
        )
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "first"},
            "text": "A question about this passage.",
        },
    )["id"]
    page = open_page(browser, url)
    page.locator("#origin").click()
    entries = page.evaluate("history.length")
    page.keyboard.press("t")
    expect(page.locator(f'.lf-margin-preview [data-thread="{root}"]')).to_be_focused()
    # Card focus precedes the passage's smooth scroll; observe its arrival first.
    expect(page.locator("#first-reading span")).to_be_in_viewport()
    scroll_settled(page)
    expect(page.locator("#first-reading span")).to_be_visible()
    assert page.locator("#first-reading span").evaluate(
        "el => {const r=el.getBoundingClientRect(); return r.bottom > 60 && r.top < innerHeight-60}"
    ), "the words checked must be the actual rendered landing"
    page.locator("#first-reading span").click()
    page.locator("#reading-control").click()
    panel_menu(page)
    page.keyboard.press("Escape")
    page.keyboard.press("m")
    expect(page.locator("#second")).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("history.length") == entries + 1
    page.go_back()
    expect(page.locator("#origin")).to_be_focused()
    page.wait_for_function("scrollY < 100")


@pytest.mark.parametrize("moved", ["inline", "breakpoint"])
def test_a_reading_finds_words_drawn_outside_their_blocks_box(browser, serve, moved):
    """A block whose own box lies below the window can still draw words in it, through a
    positioned child. A reading of the screen passes over a block only when its words
    are drawn inside its box, so the words the reader sees name the place, including
    once a breakpoint moves the child after an earlier reading, with no change to the
    page's text."""
    style = "position: absolute; top: 200px; left: 0" if moved == "inline" else ""
    source = leaf_page(
        "Words outside their block",
        "<style>@media (width < 800px) {"
        " #drawn { position: absolute; top: 200px; left: 0 } }</style>"
        '<div style="position: relative">'
        '<div style="height: 1400px"></div>'
        '<p id="carrier">The carrier paragraph sits far below the window.'
        f'<span id="drawn" style="{style}">'
        "These positioned words are drawn in the window.</span></p>"
        "</div>"
        + "".join(f"<p>Later paragraph {n} below the carrier.</p>" for n in range(5)),
    )
    page = open_page(browser, serve(source))
    resized(page, 1000, 600)
    rendered(page)
    first = """async () => {
      const rp = await window.__lfCheckApi();
      return rp.readingBlock()?.id ?? null;
    }"""
    if moved == "breakpoint":
        assert page.evaluate(first) is None
        resized(page, 700, 600)
        rendered(page)
    assert page.evaluate(first) == "carrier"


@pytest.mark.parametrize("separated", [False, True])
def test_reading_landmarks_use_drawn_segments_in_mixed_blocks(
    browser, serve, separated
):
    """Hidden words cannot put an offscreen passage into a reading checkpoint.
    Once its drawn words are read, the checkpoint quotes and restores those words."""
    visible = "These are the actual visible words of the mixed paragraph."
    earlier = (
        "<span>These earlier visible words stand above the concealed space.</span>"
        if separated
        else ""
    )
    url = serve(
        leaf_page(
            "A drawn reading landmark",
            '<h1 id="origin">Reading before the mixed paragraph begins.</h1>'
            f'<p id="mixed">{earlier}<span id="concealed" '
            'style="visibility:hidden;display:block;height:1400px">'
            "These concealed words are not what the reader can see.</span>"
            f'<span id="visible">{visible}</span></p>'
            '<div style="height:1800px"></div>'
            '<p id="destination">The distant discussion after the reading place.</p>'
            '<div style="height:900px"></div>',
        )
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "destination"},
            "text": "A question about the distant passage.",
        },
    )["id"]
    page = open_page(browser, url)
    if separated:
        page.evaluate("scrollTo({top:500, behavior:'instant'})")
        scroll_settled(page)
    reading = """async () => {
      const owner = await window.__lfCheckApi();
      return {blocks: [...owner.blocksOnScreen()].map(([block]) => block.id),
        place: (await window.__lfWidgetApi()).capturePlace(), top: document.querySelector('#visible').getBoundingClientRect().top};
    }"""
    initial = page.evaluate(reading)
    assert "mixed" not in initial["blocks"]
    assert initial["place"].get("quote") == (
        None if separated else "Reading before the mixed paragraph begins."
    )
    page.locator("#visible").click()
    scroll_settled(page)
    chosen = page.evaluate(reading)
    assert chosen["place"]["quote"] == visible
    chosen_scroll = page.evaluate("scrollY")
    page.keyboard.press("t")
    expect(page.locator(f'.lf-margin-preview [data-thread="{root}"]')).to_be_focused()
    scroll_settled(page)
    page.go_back()
    page.wait_for_function("top => Math.abs(scrollY-top) <= 2", arg=chosen_scroll)
    returned = page.evaluate(reading)
    assert returned["place"]["quote"] == visible
    assert returned["top"] == pytest.approx(chosen["top"], abs=2)


def test_reading_place_keeps_a_projected_row_among_repeated_words(browser, serve):
    """A long text block's row identity survives capture, serialization and reflow."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reading a projected row",
                '<h1>Projected text</h1><pre id="rows">'
                + "".join(
                    f'<span id="row-{n}" style="display:block">'
                    "The same words occur on every independently addressed row.</span>"
                    for n in range(80)
                )
                + '</pre><div style="height:900px"></div>',
            )
        ),
    )
    page.evaluate("""() => {
      for (const row of document.querySelector('#rows').children) {
        row.dataset.lfProjection = 'rows';
        row.dataset.lfDatum = row.id;
      }
      window.scrollBy(0, document.querySelector('#row-40').getBoundingClientRect().top - 100);
    }""")
    scroll_settled(page)
    reading = page.evaluate("""async () => {
      const api = await window.__lfWidgetApi();
      const place = api.capturePlace();
      return {place, top: document.getElementById(place.datum)?.getBoundingClientRect().top};
    }""")
    assert reading["place"].get("datum"), reading
    assert reading["place"]["quote"].startswith("The same words")
    assert reading["top"] is not None
    # A serialized checkpoint has no live node to disguise a lost datum identity.
    page.evaluate("""() => {
      document.querySelector('#row-0').style.height = '400px';
      window.scrollTo({top: 0, behavior: 'instant'});
    }""")
    scroll_settled(page)
    page.evaluate(
        """async place => {
      (await window.__lfWidgetApi()).restorePlace(place);
    }""",
        reading["place"],
    )
    scroll_settled(page)
    assert page.locator(f"#{reading['place']['datum']}").bounding_box()[
        "y"
    ] == pytest.approx(reading["top"], abs=2)


def test_reading_place_visits_a_projected_passage_before_its_parent_continuation(
    browser, serve
):
    """A paragraph's later words cannot precede the datum that splits its reading."""
    record = (
        "The projected record is the first visible passage the reader should keep. "
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A projected passage inside a paragraph",
                '<section id="source"><p id="paragraph">'
                '<span style="display:block;height:1100px">Earlier paragraph words.</span>'
                '<span id="record" style="display:block">'
                + record
                * 4
                + '</span><span style="display:block">'
                "The later continuation follows the record and must not take its place."
                '</span></p></section><div style="height:900px"></div>',
            )
        ),
    )
    page.evaluate("""() => {
      const record = document.querySelector('#record');
      record.dataset.lfGen = '1';
      record.dataset.lfProjection = 'source';
      record.dataset.lfDatum = 'record';
      window.scrollBy(0, record.getBoundingClientRect().top - 80);
    }""")
    scroll_settled(page)
    place = page.evaluate(
        """async () => (await window.__lfWidgetApi()).capturePlace()"""
    )
    assert place.get("datum") == "record", place
    assert place["quote"].startswith(record)


def test_reading_restore_leaves_a_concealed_landmark_alone(browser, serve, subtests):
    """Restoring a serialized landmark never travels to concealed zero geometry. Each
    case conceals a landmark of its own, so the cases share one page."""
    words = "The review result whose position the reader saved earlier."
    cases = [
        (conceal, quote)
        for conceal in ("display", "visibility")
        for quote in (False, True)
    ]
    landmarks = "".join(
        '<div style="height:1600px"></div>'
        f'<section id="landmark-{conceal}-{quote:d}" style="display:contents">'
        f"<p>{words}</p></section>"
        for conceal, quote in cases
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Concealed reading landmark",
                f'<h1>Review</h1>{landmarks}<div style="height:2000px"></div>',
            )
        ),
    )
    for conceal, quote in cases:
        with subtests.test(conceal=conceal, quote=quote):
            result = page.evaluate(
                """async ({identity, words, conceal, quote}) => {
              const {restorePlace} = await window.__lfWidgetApi();
              const {landingBand, shownBox} = await window.__lfCheckApi();
              const section = document.getElementById(identity);
              const place = {section: section.id, sectionTop: 0};
              if (quote) Object.assign(place, {quote: words, quoteTop: 0});
              restorePlace(place);
              const range = document.createRange();
              range.selectNodeContents(section.firstElementChild);
              const visible = quote ? range.getBoundingClientRect().top : shownBox(section).top;
              const band = landingBand(document.scrollingElement).top;
              section.style[conceal] = conceal === 'display' ? 'none' : 'hidden';
              scrollTo({top:800, behavior:'instant'});
              const before = scrollY;
              restorePlace(place);
              return {visible, band, before, after:scrollY};
            }""",
                {
                    "identity": f"landmark-{conceal}-{quote:d}",
                    "words": words,
                    "conceal": conceal,
                    "quote": quote,
                },
            )
            assert result["visible"] == pytest.approx(result["band"], abs=2)
            assert result["before"] == result["after"]


def test_back_returns_from_an_obligation_the_walk_travelled_to(browser, serve):
    """The obligation walk records the same history the thread walk does: one entry for a
    navigation group visiting obligations somewhere else however far it goes, so Back returns to where the
    user was reading before it, and a navigation group that crosses from threads to obligations is
    still one navigation group."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back from an ask",
            f"""
<h1 id="h">Back from an ask</h1>
<section id="near"><p>A question sits at the top.</p></section>
<lf-ask id="first-decision"><h2>Where should the feeders go?</h2>
<lf-options id="first" choose>
  <lf-option id="fi-hedge"><strong>Along the hedge</strong></lf-option>
  <lf-option id="fi-lawn"><strong>Out on the lawn</strong></lf-option>
</lf-options></lf-ask>
<section id="above">{filler}</section>
<lf-ask id="second-decision"><h2>Who fills them?</h2>
<lf-options id="second" choose>
  <lf-option id="se-rota"><strong>A rota</strong></lf-option>
  <lf-option id="se-camera"><strong>Whoever the camera calls</strong></lf-option>
</lf-options></lf-ask>
<section id="below">{filler}</section>
""",
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "above"},
            "text": "A question about the filler.",
        },
    )
    page = open_page(browser, url)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()
    # Focus precedes the outer scroll, so observe movement before waiting for rest.
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=reading
    )
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    page.keyboard.press("Shift+m")
    expect(page.locator("#first-decision")).to_be_focused()
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=landed
    )
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked < landed - 1000
    assert page.evaluate("history.length") == entries + 1

    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )

    # From the bottom again: `t` travels to the thread just below the first obligation, and
    # `m` from there to the second continues that navigation group rather than starting another,
    # so one Back skips the thread's landing and returns to the bottom.
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    page.keyboard.press("t")
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    scroll_settled(page)
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    scroll_settled(page)
    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )


def test_back_returns_from_an_obligation_whose_context_the_arrival_brings_in(
    browser, serve
):
    """An obligation in front of the user whose arrival region is not still moves the page,
    since the arrival puts the region's start at the top of the window, and a press
    that moves the page records where the user was reading. A draft declares no region,
    so its region runs up from the heading its context starts under."""
    context = "".join(f"<p>Context paragraph {n}.</p>" for n in range(8))
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(40))
    url = serve(
        leaf_page(
            "Back from a draft",
            f"""
<h1 id="h">Back from a draft</h1>
<section id="above">{filler}</section>
<h2 id="context">The invitation</h2>
{context}
<lf-draft id="note" needed><pre>The sample workshop is in the blue room.</pre></lf-draft>
<section id="below">{filler}</section>
""",
        )
    )
    page = open_page(browser, url)
    page.evaluate(
        "document.scrollingElement.scrollBy({top: document.getElementById('note')"
        ".getBoundingClientRect().top - 70, behavior: 'instant'})"
    )
    assert page.evaluate(
        "document.getElementById('context').getBoundingClientRect().bottom < 0"
    )
    reading = page.evaluate("document.scrollingElement.scrollTop")
    entries = page.evaluate("history.length")

    page.keyboard.press("m")
    expect(page.locator("#note")).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("document.scrollingElement.scrollTop") < reading - 100
    assert page.evaluate("history.length") == entries + 1
    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )


RESTORE_SELECTION_PAGE = leaf_page(
    "restore selection",
    """
    <h1>Selected words</h1>
    <section id="passages">
      <details id="selected-details" open><summary>The selected passage</summary>
        <p id="remembered">The amber passage keeps <strong>its own identity</strong>.</p>
      </details>
      <p id="other">The violet passage belongs to another subject.</p>
    </section>
    <textarea id="native" aria-label="Native editor">Editor words</textarea>
    <div style="height: 1400px"></div><p id="away">Another reading place.</p>
    <a id="away-link" href="#remembered">Back to the passage</a>
    """,
)


def _select_remembered_backwards(page):
    """A native backwards drag, including the passage's inline markup."""
    box = page.locator("#remembered").evaluate("""node => {
        const range = document.createRange(); range.selectNodeContents(node);
        const box = range.getBoundingClientRect();
        return {left: box.left, right: box.right, y: box.top + box.height / 2};
    }""")
    select(page, (box["right"] - 1, box["y"]), (box["left"], box["y"]))
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.wait_for_function(
        "() => getSelection().toString() === "
        "'The amber passage keeps its own identity.'"
    )
    assert page.evaluate("""() => {
        const selection = getSelection(), probe = document.createRange();
        probe.setStart(selection.anchorNode, selection.anchorOffset);
        return probe.compareBoundaryPoints(Range.START_TO_START, selection.getRangeAt(0)) > 0;
    }""")


def _word_point(locator, word):
    """Place an actual gesture over letters, avoiding blank space in a block's box."""
    return locator.evaluate(
        """(node, sought) => {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      let word; while ((word = walker.nextNode()) && !word.data.includes(sought)) {}
      const range = document.createRange(), start = word.data.indexOf(sought);
      range.setStart(word, start); range.setEnd(word, start + sought.length);
      const box = range.getBoundingClientRect();
      return {x: box.left + box.width / 2, y: box.top + box.height / 2};
    }""",
        word,
    )


ALIGN_CURRENT_PAGE = leaf_page(
    "Align the current item",
    '<h1>Keep the same reading place</h1><div style="height:700px"></div>'
    '<lf-ask id="align-ask"><h2>Which plan should we keep?</h2>'
    '<lf-options id="align-options" choose><lf-option id="align-yes">Yes</lf-option>'
    '<lf-option id="align-no">No</lf-option></lf-options></lf-ask>'
    '<h2 id="align-heading" tabindex="0">The current heading</h2>'
    '<p id="remembered">The amber passage keeps <strong>its own identity</strong>.</p>'
    '<textarea id="native" aria-label="Native editor">Editor words</textarea>'
    '<a href="#align-heading">A Go-to destination</a><div style="height:1400px"></div>',
)


def _expect_aligned(
    page, target, scroller="document.scrollingElement", *, exact_margin=True
):
    """The item's opening clears its reading area's pinned furniture."""
    page.evaluate("async () => { window.__lfAlignApi = await window.__lfCheckApi(); }")
    page.wait_for_function(
        """({target, scroller, exact_margin}) => {
          const {landingBand, shownBox} = window.__lfAlignApi;
          const item = document.querySelector(target), box = eval(scroller);
          const offset = shownBox(item).top - landingBand(box).top;
          const margin = parseFloat(getComputedStyle(item).scrollMarginTop) || 0;
          return exact_margin ? Math.abs(offset - margin) < 2
            : offset > -2 && offset < margin + 2;
        }""",
        arg={"target": target, "scroller": scroller, "exact_margin": exact_margin},
    )


def test_align_current_item_keeps_obligation_control_heading_selection_and_history(
    browser, serve
):
    page = open_page(browser, serve(ALIGN_CURRENT_PAGE))
    page.keyboard.press("m")
    expect(page.locator("#align-ask")).to_be_focused()
    page.locator("#align-yes").get_by_role("checkbox").focus()
    expect(page.locator("#align-yes").get_by_role("checkbox")).to_be_focused()
    page.evaluate("scrollBy(0, -180)")
    history = page.evaluate(
        "[history.length, navigation.currentEntry.key, location.href]"
    )
    # Help teaches the complete sequence while its command remains executable from
    # the unarmed page through the same capability's touch route.
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    page.get_by_role("combobox", name="Search commands").fill("g z")
    alignment = reference.locator('[role=option][data-lf-command="reading.align.top"]')
    expect(alignment.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "z"])
    alignment.click()
    expect(reference).to_be_hidden()
    # The reference hands focus back before the current-location paint. Its command can align
    # before the ring supplies a scroll margin; either landing clears the pinned band.
    _expect_aligned(page, "#align-ask", exact_margin=False)
    expect(page.locator("#align-yes").get_by_role("checkbox")).to_be_focused()
    page.evaluate("scrollBy(0, -180)")
    page.keyboard.press("g")
    page.keyboard.press("z")
    _expect_aligned(page, "#align-ask")
    expect(page.locator("#align-yes").get_by_role("checkbox")).to_be_focused()
    assert (
        page.evaluate("[history.length, navigation.currentEntry.key, location.href]")
        == history
    )
    page.locator("#align-heading").focus()
    page.keyboard.press("g")
    page.keyboard.press("z")
    _expect_aligned(page, "#align-heading")
    expect(page.locator("#align-heading")).to_be_focused()
    page.locator("#remembered").scroll_into_view_if_needed()
    _select_remembered_backwards(page)
    page.evaluate("""() => {
      const selection = getSelection();
      window.beforeAlign = [selection.anchorNode, selection.anchorOffset,
        selection.focusNode, selection.focusOffset, document.activeElement];
      scrollBy(0, -120);
    }""")
    page.keyboard.press("g")
    page.keyboard.press("z")
    _expect_aligned(page, "#remembered")
    assert page.evaluate("""() => {
      const selection = getSelection();
      return [selection.anchorNode, selection.anchorOffset, selection.focusNode,
        selection.focusOffset, document.activeElement].every((v,i) => v === beforeAlign[i]);
    }""")
    page.locator("#native").focus()
    page.keyboard.type("gz")
    expect(page.locator("#native")).to_have_value("gzEditor words")


def test_align_current_item_uses_bounded_reading_region_and_preserves_horizontal_position(
    browser, serve
):
    source = leaf_page(
        "Bounded alignment",
        "<h1>Outside reading</h1><p>Unrelated page words remain where they were.</p>"
        '<div id="inspection" data-bound="start" style="height:300px;overflow:auto;scroll-padding-top:36px">'
        '<div style="height:300px;width:1400px"></div>'
        '<h2 id="nested-heading" tabindex="0">An inspection heading</h2>'
        '<p id="nested-reading">A bounded paragraph stays with its own reading region.</p>'
        '<div style="height:900px"></div></div><div style="height:900px"></div>',
    )
    page = open_page(browser, serve(source))
    page.locator("#nested-heading").focus()
    page.locator("#inspection").evaluate(
        "box => {box.scrollTop=180; box.scrollLeft=90}"
    )
    root_y = page.evaluate("scrollY")
    page.keyboard.press("g")
    page.keyboard.press("z")
    _expect_aligned(page, "#nested-heading", "document.querySelector('#inspection')")
    assert page.locator("#inspection").evaluate("box => box.scrollLeft") == 90
    assert page.evaluate("scrollY") == root_y
    expect(page.locator("#nested-heading")).to_be_focused()
    # A click and collapsed caret still identify the paragraph in this region.
    point = _word_point(page.locator("#nested-reading"), "bounded")
    page.mouse.click(point["x"], point["y"])
    page.keyboard.press("g")
    page.keyboard.press("z")
    _expect_aligned(page, "#nested-reading", "document.querySelector('#inspection')")


# The leaf's menu lists Align under Navigate where no keyboard reaches its keys.
ALIGN_ROW = "command:reading.align.top"


def test_align_current_item_from_the_menu_on_touch_reserves_z(browser, serve):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(ALIGN_CURRENT_PAGE), context=context)
    page.keyboard.press("m")
    page.locator("#align-yes").get_by_role("checkbox").focus()
    expect(page.locator("#align-yes").get_by_role("checkbox")).to_be_focused()
    page.evaluate("scrollBy(0,-160)")
    control = panel_control(page, ALIGN_ROW, at="navigate")
    expect(control).to_be_enabled()
    press_visible(page, control, touch=True)
    # Returning focus from the menu can align before the current-location paint
    # supplies its scroll margin, just as activation from the command reference does.
    # Both landings must clear the pinned band.
    _expect_aligned(page, "#align-ask", exact_margin=False)
    page.locator("#align-heading").focus()
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    codes = page.locator(CHIPS).evaluate_all(
        "nodes => nodes.map(node => node.dataset.lfHintCode)"
    )
    assert codes and all("z" not in code for code in codes)
    page.keyboard.press("Escape")
    point = _word_point(page.locator("#remembered"), "amber")
    page.mouse.dblclick(point["x"], point["y"])
    page.evaluate("""() => {
      const s = getSelection();
      window.beforeAlign = [s.anchorNode,s.anchorOffset,s.focusNode,s.focusOffset];
      scrollBy(0,-80);
    }""")
    panel_control(page, ALIGN_ROW, at="navigate").tap()
    _expect_aligned(page, "#remembered")
    assert page.evaluate("""() => {
      const s = getSelection();
      return [s.anchorNode,s.anchorOffset,s.focusNode,s.focusOffset].every((v,i) => v === beforeAlign[i]);
    }""")
    page.locator("#native").focus()
    page.keyboard.type("gz")
    expect(page.locator("#native")).to_have_value("gzEditor words")


def test_the_menu_keeps_its_place_when_a_revision_shortens_the_words_it_held(
    browser, serve
):
    """The leaf's menu holds the reader's caret while it is open, and a live revision can
    shorten the very text node that caret stands in meanwhile. A place-keeping command
    then hands back what is left of that place and acts, rather than throwing on an
    offset past the node's new length. The menu lists Align under Navigate where no
    keyboard reaches it, so the reader here has a touch screen."""
    source = leaf_page(
        "A shortened passage",
        '<h1>Keep the same reading place</h1><div style="height:700px"></div>'
        '<p id="remembered">The amber passage keeps <strong>its own identity</strong>.</p>'
        '<div style="height:1400px"></div>',
    )
    context = browser.new_context(has_touch=True)
    page = open_page(browser, live_url(serve(source)), context=context)
    point = _word_point(page.locator("#remembered"), "keeps")
    page.mouse.click(point["x"], point["y"])
    held = page.evaluate(
        "() => { window.held = getSelection().focusNode; return getSelection().focusOffset; }"
    )
    control = panel_control(page, "command:reading.align.top", at="navigate")

    stamp = stamp_page(
        serve.page_dir,
        source.replace("The amber passage keeps ", "Amber "),
        "Shorten the passage",
    )
    wait_for_revision(page, stamp["revision"])
    # The revision rewrote the held node in place, leaving the caret's offset past it.
    assert page.evaluate("() => window.held.isConnected && window.held.length") < held
    control.click()
    _expect_aligned(page, "#remembered")


def test_align_current_thread_stays_in_its_panel_without_travel(browser, serve):
    page = open_page(
        browser, serve(ALIGN_CURRENT_PAGE, anchored=[("remembered", "amber")] * 8)
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    row = page.locator(".lf-fp-thread").nth(4)
    row.focus()
    rendered(page)
    before = page.evaluate(
        "[scrollY,history.length,navigation.currentEntry.key,location.href]"
    )
    page.keyboard.press("g")
    page.keyboard.press("z")
    rendered(page)
    expect(row).to_be_focused()
    panel_settled(page, view="threads")
    assert (
        page.evaluate(
            "[scrollY,history.length,navigation.currentEntry.key,location.href]"
        )
        == before
    )


def test_a_box_is_already_shown_whole_where_it_fits_and_in_part_where_it_cannot(
    browser, serve
):
    """A landing that follows the user moves nothing for a box already shown: all of it
    in view where it fits its room, any of it where it does not. A wrapper clipping only
    sideways bounds no height, so an editor standing in an `overflow-x: clip` row 20px
    tall still fits, and 30px of it in view is not yet shown."""
    source = leaf_page(
        "Room",
        '<div style="height:2000px"></div>'
        '<div style="overflow-x:clip;height:20px"><div id="box" style="height:100px"></div></div>'
        '<div style="height:2000px"></div><div id="tall" style="height:5000px"></div>',
    )
    page = open_page(browser, serve(source))
    reading = page.evaluate("""async () => {
      const {alreadyShown, fitsWhole} =
        await window.__lfCheckApi();
      const {shownWindow} = await window.__lfWidgetApi();
      const partly = (node) => {
        const top = node.getBoundingClientRect().top - (shownWindow().bottom - 30);
        scrollBy({top, behavior: 'instant'});
        return [fitsWhole(node), alreadyShown(node)];
      };
      return [partly(document.querySelector('#box')),
              partly(document.querySelector('#tall'))];
    }""")
    assert reading == [[True, False], [False, True]]


def test_align_current_tall_block_reveals_its_opening_through_outer_scrollers(
    browser, serve
):
    source = leaf_page(
        "A tall current item",
        '<h1>Read the opening</h1><div style="height:600px"></div>'
        '<div id="inspection" data-bound="start" style="height:300px;overflow:auto;scroll-padding-top:24px">'
        '<pre id="tall" tabindex="0">'
        + "A line in the current item.\n"
        * 80
        + '</pre><div style="height:600px"></div></div>'
        '<div style="height:1400px"></div>',
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce")
    page.locator("#tall").focus()
    page.evaluate("""async () => {
      const {landingBand} = await window.__lfCheckApi();
      const box = document.querySelector('#inspection');
      const docY = box.getBoundingClientRect().top + scrollY;
      scrollTo(0, docY - landingBand(document.scrollingElement).top + 80);
      box.scrollTop = 300;
    }""")
    scroll_settled(page)
    history = page.evaluate("[history.length,navigation.currentEntry.key]")
    assert page.locator("#tall").bounding_box()["y"] < 0
    page.keyboard.press("g")
    page.keyboard.press("z")
    scroll_settled(page, "#inspection")
    _expect_aligned(page, "#tall")
    expect(page.locator("#tall")).to_be_focused()
    assert page.locator("#inspection").evaluate("box => box.scrollTop") == 0
    assert page.evaluate("[history.length,navigation.currentEntry.key]") == history


def test_end_landing_reveals_a_tall_items_closing_edge_through_outer_scrollers(
    browser, serve
):
    """A tall item's closing edge travels through both its pane and the outer pane."""
    source = leaf_page(
        "Read the closing edge",
        "<h1>Nested reading</h1>"
        '<div id="outer-reading" data-bound="start" style="height:300px;overflow:auto">'
        '<div style="height:300px"></div>'
        '<div id="inner-reading" data-bound="start" style="height:250px;overflow:auto">'
        '<pre id="tall-ending" style="margin:0">'
        + "A line in the current item.\n"
        * 80
        + '</pre><div style="height:400px"></div></div>'
        '<div style="height:500px"></div></div>'
        '<div style="height:1000px"></div>',
    )
    page = open_page(browser, serve(source))
    reading = page.evaluate("""async () => {
      const {scrollIntoView} = await window.__lfWidgetApi();
      const {landingBand} = await window.__lfCheckApi();
      const target = document.querySelector('#tall-ending');
      const inner = document.querySelector('#inner-reading');
      const outer = document.querySelector('#outer-reading');
      scrollIntoView(target, {block:'end', behavior:'instant'});
      return {
        ending: target.getBoundingClientRect().bottom,
        height: target.getBoundingClientRect().height,
        bands: [inner, outer, document.scrollingElement].map(landingBand),
        offsets: [inner.scrollTop, outer.scrollTop],
      };
    }""")
    assert reading["height"] > 2 * 300, (
        "the destination must span its outer reading band"
    )
    assert all(offset > 0 for offset in reading["offsets"]), reading
    assert all(
        band["top"] <= reading["ending"] <= band["bottom"] + 1
        for band in reading["bands"]
    ), reading


# Each turn once and each alignment once.
@pytest.mark.parametrize(
    ("alignment", "quarter_turn"), [("nearest", "enclosing"), ("start", "owning")]
)
def test_vertical_landing_crosses_a_quarter_turn_without_changing_horizontal_reading(
    browser, serve, quarter_turn, alignment
):
    """A local vertical axis that cannot move screen Y leaves travel to the outer region."""
    target = (
        '<p id="quarter-target" tabindex="0" '
        'style="width:120px;height:30px;margin:0 0 0 40px">Opening words</p>'
        '<div style="width:600px;height:1200px"></div>'
    )
    inner = (
        '<div id="quarter-inner" data-bound="start" '
        'style="width:180px;height:180px;overflow:auto;margin-left:40px;'
        'transform:translateY(180px) rotate(-90deg);transform-origin:left top">'
        + target
        + '</div><div style="width:600px;height:1200px"></div>'
    )
    source = leaf_page(
        "Vertical travel through a quarter turn",
        '<h1>Reveal the reading place</h1><div style="height:900px"></div>'
        '<div id="quarter-port" data-bound="start" '
        'style="width:300px;height:300px;overflow:auto;'
        'transform:translateX(300px) rotate(90deg);transform-origin:left top">'
        + (target if quarter_turn == "owning" else inner)
        + '</div><div style="height:1600px"></div>',
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce")
    before = page.evaluate("""async () => {
      const {scrollAxes} = await window.__lfCheckApi();
      const {scrollersOf} = await window.__lfCheckApi();
      const target = document.querySelector('#quarter-target');
      const boxes = [...scrollersOf(target)].filter(box => box !== document.scrollingElement);
      for (const box of boxes) box.scrollLeft = 13;
      target.focus({preventScroll:true});
      return {top:target.getBoundingClientRect().top, height:innerHeight,
        axes:boxes.map(box => scrollAxes(box).y.y),
        offsets:boxes.map(box => [box.scrollLeft, box.scrollTop]),
        history:[history.length, navigation.currentEntry.key, location.href]};
    }""")
    assert before["top"] > before["height"]
    assert before["axes"] == ([0] if quarter_turn == "owning" else [1, 0])
    assert all(left > 0 for left, _ in before["offsets"])
    if alignment == "start":
        page.keyboard.press("g")
        page.keyboard.press("z")
    else:
        page.evaluate("""async () => {
          const {scrollIntoReadingBand} = await window.__lfWidgetApi();
          const target = document.querySelector('#quarter-target');
          scrollIntoReadingBand(target, target, 'nearest', 'instant');
        }""")
    after = page.evaluate("""async () => {
      const {landingBand} = await window.__lfCheckApi();
      const {scrollersOf} = await window.__lfCheckApi();
      const target = document.querySelector('#quarter-target');
      return {rect:target.getBoundingClientRect().toJSON(), band:landingBand(document.scrollingElement),
        offsets:[...scrollersOf(target)].filter(box => box !== document.scrollingElement)
          .map(box => [box.scrollLeft, box.scrollTop]),
        history:[history.length, navigation.currentEntry.key, location.href]};
    }""")
    assert after["rect"]["top"] >= after["band"]["top"] - 1
    extent = (
        after["rect"]["top"] + 1 if alignment == "start" else after["rect"]["bottom"]
    )
    assert extent <= after["band"]["bottom"] + 1
    assert after["offsets"] == before["offsets"]
    assert after["history"] == before["history"]
    expect(page.locator("#quarter-target")).to_be_focused()


def test_align_current_item_does_not_follow_old_page_caret_from_empty_threads(
    browser, serve
):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(ALIGN_CURRENT_PAGE), context=context)
    page.locator("#remembered").scroll_into_view_if_needed()
    point = _word_point(page.locator("#remembered"), "amber")
    page.mouse.click(point["x"], point["y"])
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    threads = page.locator(panel_view("threads"))
    expect(threads).to_be_focused()
    page.wait_for_function("getSelection().isCollapsed")
    before = page.evaluate("[scrollY,history.length,navigation.currentEntry.key]")
    page.keyboard.press("g")
    page.keyboard.press("z")
    expect(threads).to_be_focused()
    assert (
        page.evaluate("[scrollY,history.length,navigation.currentEntry.key]") == before
    )


def test_align_current_obligation_in_a_reply_keeps_its_question_extent(browser, serve):
    url = serve(ALIGN_CURRENT_PAGE, anchored=[("remembered", "amber")] * 8)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": roots[4],
            "revision": 1,
            "text": "Choose the follow-up.",
            "markup": '<lf-ask id="reply-ask"><h3>Which follow-up should be ready?</h3>'
            '<lf-options id="reply-options" choose><lf-option id="reply-yes">Ready</lf-option>'
            '<lf-option id="reply-no">Wait</lf-option></lf-options></lf-ask>',
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, roots[4])
    control = view.locator('lf-option[id="reply-yes"]').get_by_role("checkbox")
    control.focus()
    before = page.evaluate("[scrollY,history.length,navigation.currentEntry.key]")
    page.keyboard.press("g")
    page.keyboard.press("z")
    rendered(page)
    expect(control).to_be_focused()
    assert (
        page.evaluate("[scrollY,history.length,navigation.currentEntry.key]") == before
    )


def test_restore_selection_reveals_backward_passage_and_keeps_native_editing(
    browser, serve
):
    """A remembered semantic passage returns through shared travel, with its working end."""
    page = open_page(browser, serve(RESTORE_SELECTION_PAGE))
    _select_remembered_backwards(page)
    page.keyboard.press("Escape")
    page.locator("#selected-details summary").click()
    page.locator("#away").scroll_into_view_if_needed()
    page.keyboard.press("g")
    # Direct destinations own the hint alphabet: lower-case v cannot name a page item.
    expect(page.locator(CHIPS).first).to_be_visible()
    codes = page.locator(CHIPS).evaluate_all(
        "nodes => nodes.map(node => node.dataset.lfHintCode)"
    )
    assert codes
    assert all("v" not in code for code in codes)
    page.keyboard.press("v")
    expect(page.locator("#selected-details")).to_have_attribute("open", "")
    page.wait_for_function(
        "() => getSelection().toString() === "
        "'The amber passage keeps its own identity.'"
    )
    assert page.evaluate("""() => {
        const selection = getSelection(), probe = document.createRange();
        probe.setStart(selection.anchorNode, selection.anchorOffset);
        return probe.compareBoundaryPoints(Range.START_TO_START, selection.getRangeAt(0)) > 0;
    }""")
    assert page.locator("#remembered").bounding_box()["y"] < 700

    # Programmatic Back restores the source place but must not choose a new passage.
    page.go_back()
    page.wait_for_function("() => scrollY > 700")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function(
        "() => getSelection().toString() === "
        "'The amber passage keeps its own identity.'"
    )

    # A native editor owns its letters and selections; leaving it keeps the prose target.
    native = page.locator("#native")
    native.focus()
    native.select_text()
    page.keyboard.type("gv")
    expect(native).to_have_value("gv")
    page.keyboard.press("Escape")
    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function(
        "() => getSelection().toString() === "
        "'The amber passage keeps its own identity.'"
    )
    assert page.evaluate("""() => {
        const selection = getSelection(), probe = document.createRange();
        probe.setStart(selection.anchorNode, selection.anchorOffset);
        return probe.compareBoundaryPoints(Range.START_TO_START, selection.getRangeAt(0)) > 0;
    }""")
    # Native extension acts on the restored working end. A keyboard selection then
    # becomes the next remembered passage, with the same direction.
    page.keyboard.press("Shift+ArrowRight")
    page.wait_for_function(
        "() => getSelection().toString() === 'he amber passage keeps its own identity.'"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function(
        "() => getSelection().toString() === 'he amber passage keeps its own identity.'"
    )
    assert take_browser_errors(page) == []


def test_restore_selection_rebinds_revisions_and_refuses_missing_words(browser, serve):
    """A replaced node is irrelevant; deletion refuses without choosing another subject."""
    url = serve(RESTORE_SELECTION_PAGE)
    page = open_page(browser, live_url(url))
    _select_remembered_backwards(page)
    page.keyboard.press("Escape")
    revised = RESTORE_SELECTION_PAGE.replace(
        "<strong>its own identity</strong>", "<em>its own identity</em>"
    )
    _publish(serve.page_dir, 2, revised, "new inline markup")
    told(page)
    expect(page.locator("#remembered em")).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function(
        "() => getSelection().toString() === "
        "'The amber passage keeps its own identity.'"
    )
    assert page.evaluate("""() => {
        const selection = getSelection(), probe = document.createRange();
        probe.setStart(selection.anchorNode, selection.anchorOffset);
        return probe.compareBoundaryPoints(Range.START_TO_START, selection.getRangeAt(0)) > 0;
    }""")
    page.keyboard.press("Escape")
    missing = revised.replace(
        "The amber passage keeps <em>its own identity</em>.",
        "The original subject was removed.",
    )
    _publish(serve.page_dir, 3, missing, "removed that passage")
    told(page)
    expect(page.locator("#remembered")).to_have_text(
        "The original subject was removed."
    )
    page.keyboard.press("g")
    page.keyboard.press("v")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", "That selected passage is unavailable on this version"
    )
    assert page.evaluate("() => getSelection().toString()") == ""

    # Both copies have the original context. Refusal keeps the remembered identity
    # rather than choosing the first occurrence by order.
    duplicated = revised.replace(
        '<p id="remembered">The amber passage keeps <em>its own identity</em>.</p>',
        '<p id="remembered">The selected passage '
        "The amber passage keeps <em>its own identity</em>. "
        "The violet passage belongs to another subject. The selected passage "
        '<span id="copy">The amber passage keeps <em>its own identity</em>.</span> '
        "The violet passage belongs to another subject.</p>",
    )
    _publish(serve.page_dir, 4, duplicated, "ambiguous repeated words")
    told(page)
    expect(page.locator("#copy")).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("v")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", "That selected passage is unavailable on this version"
    )
    assert page.evaluate("() => getSelection().toString()") == ""
    assert take_browser_errors(page) == []


def test_restore_selection_has_touch_route_and_does_not_carry_draft(browser, serve):
    """Selecting prose is independent of the words kept in another subject's editor."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(RESTORE_SELECTION_PAGE), context=context)
    point = _word_point(page.locator("#remembered"), "amber")
    page.mouse.dblclick(point["x"], point["y"])
    expect(selection_field(page)).to_be_visible()
    selected = page.evaluate("() => getSelection().toString()")
    assert selected
    rendered(page)
    page.keyboard.press("Escape")
    page.locator("#other").click(modifiers=["Alt"])
    editor = page.locator(".lf-fab-input")
    write(editor, "Words about the violet subject")
    page.keyboard.press("Escape")
    page.locator("#away").scroll_into_view_if_needed()
    page.locator(".lf-fp-on-user").tap()
    panel_settled(page, view="queue")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function(
        "expected => getSelection().toString() === expected", arg=selected
    )
    page.keyboard.press("Escape")
    page.locator("#away").scroll_into_view_if_needed()
    panel_control(page, "command:selection.restore", at="navigate").tap()
    page.wait_for_function(
        "expected => getSelection().toString() === expected", arg=selected
    )
    # The command closes the borrowed menu and keeps the On view open.
    expect(page.locator(PANEL)).to_have_attribute("data-open", "queue")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Words about the violet subject")
    expect(editor).to_have_attribute("aria-label", re.compile("violet"))
    page.keyboard.type("gv")
    expect(editor).to_have_js_property("value", "Words about the violet subjectgv")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(page.locator(".lf-fp-menu")).to_have_attribute("data-level", "versions")
    assert take_browser_errors(page) == []


def test_restore_selection_reveals_a_filtered_diff_datum(browser, serve):
    """The addressed widget owns filter clearance before its selected words can return."""
    page = open_page(browser, serve(DIFF_PAGE))
    line = page.locator("lf-diff [data-line]").filter(has_text="window: 60").first
    line.scroll_into_view_if_needed()
    point = _word_point(line, "window")
    page.mouse.dblclick(point["x"], point["y"])
    selected = page.evaluate("() => getSelection().toString()")
    assert selected
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("Escape")
    search = page.locator('lf-diff wa-input[name="diff-search"]')
    write(search, "Dockerfile")
    expect(line).not_to_be_visible()
    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("v")
    expect(line).to_be_visible()
    expect(search).to_have_js_property("value", "")
    page.wait_for_function(
        "expected => getSelection().toString() === expected", arg=selected
    )
    assert take_browser_errors(page) == []


@pytest.mark.parametrize("cancel", [False, True])
def test_restore_selection_failed_datum_hydration_leaves_history_untouched(
    browser, serve, cancel
):
    """A retained line key with new words is not an arrival, even after lazy loading."""
    authored = leaf_page(
        "Selected data line",
        '<h1>Review</h1><lf-diff id="patch" source="review-patch"><pre></pre>'
        '</lf-diff><div style="height:1600px"></div><p id="away">Read here.</p>',
    )
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "amber"\n'
    )
    url = serve(authored)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    page = open_page(browser, live_url(url))
    line = page.locator('lf-diff [data-lf-datum=\'["app.py","new",1]\']')
    expect(line).to_contain_text("amber")
    point = _word_point(line, "amber")
    page.mouse.dblclick(point["x"], point["y"])
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("Escape")
    page.locator("lf-diff summary").click()
    # Evidence admission precedes listing; delay the textual preparation that
    # selection travel needs after the new closed file has been presented.
    page.evaluate("""() => {
      const host = document.querySelector('#patch');
      const prepare = host.prepareEntry;
      host.prepareEntry = async function(...args) {
        await new Promise(resolve => { window.releaseSelectionDatum = resolve; });
        return prepare.apply(this, args);
      };
    }""")
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        {
            "files": [
                {
                    "path": "app.py",
                    "patch": patch.replace("amber", "violet"),
                }
            ]
        },
    )
    told(page)
    expect(line).to_have_count(0)
    page.locator("#away").scroll_into_view_if_needed()
    before = page.evaluate("({length:history.length,key:navigation.currentEntry.key})")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function("typeof releaseSelectionDatum === 'function'")
    assert (
        page.evaluate("({length:history.length,key:navigation.currentEntry.key})")
        == before
    )
    if cancel:
        page.keyboard.press("Escape")
    page.evaluate("releaseSelectionDatum()")
    expect(line).to_contain_text("violet")
    if not cancel:
        expect(panel_field(page)).to_have_attribute(
            "placeholder", "That selected passage is unavailable on this version"
        )
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert (
        page.evaluate("({length:history.length,key:navigation.currentEntry.key})")
        == before
    )
    assert page.evaluate("() => getSelection().toString()") == ""
    assert take_browser_errors(page) == []


@pytest.mark.parametrize("navigation_api", [False, True])
def test_restore_selection_back_keeps_the_offset_before_reveal(
    browser, serve, navigation_api
):
    """Disclosure can reshape the source before successful arrival commits its entry."""
    page = open_page(
        browser,
        serve(RESTORE_SELECTION_PAGE),
        init_script=None
        if navigation_api
        else "Object.defineProperty(window, 'navigation', {value:undefined});",
    )
    page.emulate_media(reduced_motion="reduce")
    _select_remembered_backwards(page)
    page.keyboard.press("Escape")
    page.locator("#selected-details summary").click()
    page.locator("#away").scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function("() => getSelection().toString().includes('amber passage')")
    assert page.evaluate("scrollY") < before - 300
    page.go_back()
    page.wait_for_function("offset => Math.abs(scrollY-offset)<2", arg=before)
    assert take_browser_errors(page) == []


def test_restore_selection_across_views_keeps_the_source_history_entry(browser, serve):
    """Exposure may rename the current URL, but Back still belongs to the source view."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Return across views",
                '<h1>Review two views</h1><lf-tabs id="views">'
                '<lf-tab id="first" label="First"><p id="remembered">'
                "The amber passage keeps <strong>its own identity</strong>.</p>"
                '<div style="height:3000px"></div></lf-tab>'
                '<lf-tab id="second" label="Second"><div style="height:1800px"></div>'
                '<p id="away">Read this other view.</p><div style="height:1300px"></div>'
                "</lf-tab></lf-tabs>",
            )
        ),
    )
    _select_remembered_backwards(page)
    page.keyboard.press("Escape")
    page.get_by_role("tab", name="Second", exact=True).click()
    page.locator("#away").click()
    before = page.evaluate(
        "({url:location.href,offset:scrollY,length:history.length,key:navigation.currentEntry.key})"
    )
    assert before["url"].endswith("#second")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function("() => getSelection().toString().includes('amber passage')")
    expect(page.get_by_role("tab", name="First", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    assert page.evaluate("location.hash") == "#first"
    assert page.evaluate("history.length") == before["length"] + 1
    page.go_back()
    expect(page.get_by_role("tab", name="Second", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    assert page.url == before["url"]
    page.wait_for_function("offset => Math.abs(scrollY-offset)<2", arg=before["offset"])
    assert page.evaluate("navigation.currentEntry.key") == before["key"]
    page.go_forward()
    expect(page.get_by_role("tab", name="First", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    page.wait_for_function("() => getSelection().toString().includes('amber passage')")
    assert take_browser_errors(page) == []


def test_restore_selection_tracks_late_native_adjustment_and_retires_write_provenance(
    browser, serve
):
    """The platform can extend a touch selection after the initial pointer ended.

    Selection.extend exercises that native endpoint transition without inventing
    page pointer events; Leaf's own writer remains a separate provenance boundary.
    Returning to a previous programmatic range is a fresh adjustment after divergence.
    """
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=True
    )
    page = open_page(browser, serve(RESTORE_SELECTION_PAGE), context=context)
    point = _word_point(page.locator("#remembered"), "identity")
    page.mouse.dblclick(point["x"], point["y"])
    expect(selection_field(page)).to_be_visible()
    initial = page.evaluate("() => getSelection().toString()")
    assert initial and initial != "amber"
    page.evaluate("""async () => {
      const word = document.querySelector('#remembered').firstChild;
      const changed = new Promise(resolve => document.addEventListener('selectionchange', resolve, {once:true}));
      getSelection().setBaseAndExtent(word, 4, word, 9);
      await changed;
    }""")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function("() => getSelection().toString() === 'amber'")
    # Restoration wrote these endpoints. Native divergence must retire that write
    # so returning to the same endpoints remembers the adjusted passage again.
    for end in (17, 9):
        page.evaluate(
            """async end => {
          const changed = new Promise(resolve => document.addEventListener('selectionchange', resolve, {once:true}));
          getSelection().extend(document.querySelector('#remembered').firstChild, end);
          await changed;
        }""",
            end,
        )
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("v")
    page.wait_for_function("() => getSelection().toString() === 'amber'")
    assert take_browser_errors(page) == []


def test_closing_a_surface_leaves_the_next_tab_where_the_user_is_reading(
    browser, serve
):
    """A step that lands the user in the document moves the Tab starting point there.

    The landing is blurred, so `activeElement` reads `body` whether or not it moved, and
    every journey that asserts only that would pass over a landing that had quietly reset
    the user to the top of the page. The press that tells them apart is the Tab after
    it: from a panel opened four screens down, it belongs on from the words in front of
    the user rather than at the document's first stop.
    """
    page = open_page(browser, serve(READING_CONTROLS_PAGE))
    page.evaluate("() => document.getElementById('p40').scrollIntoView()")
    page_at_rest(page)

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(panel_view("threads"))).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    page.keyboard.press("Tab")
    expect(page.locator("#next-control")).to_be_focused()
    # And nothing of the borrow is left on the author's paragraph.
    assert (
        page.evaluate("() => document.querySelectorAll('main [tabindex]').length") == 0
    )


def test_the_reference_hands_the_user_back_to_the_page_they_were_reading(
    browser, serve
):
    """Closing a mode gives back the press that opened it, and the user's place with it.

    A user working from the page stands on `body`: `letGo` puts them there so Space and
    PageDown reach the document's own scroll box. `?` from there recorded `body` as the
    door and closing handed focus back to it — and focusing `body` resets the browser's
    sequential focus navigation starting point, so the next Tab began at the top of the
    document. A user who opened the reference four screens down to look a key up was
    charged the whole page to get back to where they had been.

    The reading is the next Tab rather than the focused element, because that is the fact
    that was wrong: the restore itself looked fine both before and after, focus being on
    nothing either way. Authored controls before and after the reading distinguish
    restarting at the top from carrying on where the user was.
    """
    page = open_page(browser, serve(READING_CONTROLS_PAGE))
    page.evaluate("() => document.getElementById('p40').scrollIntoView()")
    page_at_rest(page)

    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-command-reference")).to_be_hidden()

    page.keyboard.press("Tab")
    expect(page.locator("#next-control")).to_be_focused()
    # And nothing of the borrow is left on the author's paragraph: `tabindex` is not in
    # PAGE_PAINT_ATTRIBUTES, so a stop left in place would be runtime paint the replay
    # signature has no vocabulary for.
    assert (
        page.evaluate("() => document.querySelectorAll('main [tabindex]').length") == 0
    )
