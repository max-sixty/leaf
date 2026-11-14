"""The reader's place: Back and Forward, reading landmarks, aligning the current item,
and restoring a remembered selection."""

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
    RELEASE_FOCUS,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
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


# A widget that draws one item at a time, as one fetching each item when it is picked
# does, so a part of another item is in no element until its item is drawn, and every
# item's parts would share their ids. It answers keys such as `b/3`, part 3 of item b,
# through the hooks every route reads (anchor-resolution.js, `revealAddressed` and
# `addressedElements`); a referrer travels to one with `navigateToDatum`.
ITEMS_LAYER = {
    "lf-items": {
        "description": "Items drawn one at a time, each part addressed by item/part.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-example": '<lf-items id="items"></lf-items>',
    },
    "lf-item-link": {
        "description": "A button that travels to one part of the items it refers to.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "for": {"type": "string"},
            "key": {"type": "string", "minLength": 1},
        },
        "required": ["id", "for", "key"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-refers": {"for": {}},
        "x-example": '<lf-item-link id="jump" for="items" key="a/1"></lf-item-link>',
    },
}
ITEMS_WIDGETS = {
    "lf-items.js": """
import {once} from '/runtime/widget-api.js';
customElements.define('lf-items', class extends HTMLElement {
  #item = null;
  connectedCallback() {
    if (once(this)) this.#draw('a');
  }
  #draw(item) {
    this.#item = item;
    this.replaceChildren(...[1, 2, 3, 4].map((part) => {
      const p = document.createElement('p');
      p.dataset.item = item;
      p.dataset.part = String(part);
      p.style.minHeight = '400px';
      p.textContent = `Item ${item}, part ${part}.`;
      return p;
    }));
  }
  lfRevealDatum(key) {
    const [item] = key.split('/');
    if (!['a', 'b'].includes(item) || item === this.#item) return null;
    return new Promise((resolve) => setTimeout(resolve, 50)).then(() => this.#draw(item));
  }
  lfElementsFor(key) {
    const [item, part] = key.split('/');
    return item === this.#item ? [...this.querySelectorAll(`[data-part="${part}"]`)] : [];
  }
});
""",
    "lf-item-link.js": """
import {navigateToDatum, once} from '/runtime/widget-api.js';
customElements.define('lf-item-link', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const button = document.createElement('button');
    button.textContent = `Open ${this.getAttribute('key')}`;
    button.addEventListener('click', () =>
      navigateToDatum(this, 'for', this.getAttribute('key')));
    this.append(button);
  }
});
""",
}


def test_a_url_naming_a_widget_key_reaches_its_part(browser, serve):
    """A URL fragment names a part of a widget by the widget's id and a key, which the
    widget draws however the URL is reached. A fresh load, a followed link, and Back and
    Forward to an entry whose item the user has since left land on the part; a reload of
    the URL `navigateToDatum` writes draws its item under the restored offset."""
    url = live_url(
        serve(
            leaf_page(
                "Items",
                """
<h1 id="top">Items</h1>
<p><a id="to-part" href="#items:a/2">Part 2 of item a</a></p>
<lf-item-link id="jump" for="items" key="b/1"></lf-item-link>
<lf-items id="items"></lf-items>
<div style="height:1600px"></div>
""",
            ),
            layer_registry=ITEMS_LAYER,
            layer_widgets=ITEMS_WIDGETS,
        )
    )

    def part(item, number):
        return page.locator(f'#items [data-item="{item}"][data-part="{number}"]')

    def landed(item, number):
        # At the window's top, where the fragment rule lands a target, rather than a
        # 400px part or more below it, where landing on the widget's top leaves it.
        target = part(item, number)
        expect(target).to_be_in_viewport()
        scroll_settled(page)
        assert 0 <= target.bounding_box()["y"] < 200

    page = open_page(browser, url + "#items:b/3")
    landed("b", 3)

    page.locator("#top").scroll_into_view_if_needed()
    page.locator("#to-part").click()
    page.wait_for_url(re.compile(r"#items:a/2$"))
    expect(part("a", 2)).to_be_focused()
    landed("a", 2)

    page.go_back()
    page.wait_for_url(re.compile(r"#items:b/3$"))
    landed("b", 3)
    page.go_forward()
    page.wait_for_url(re.compile(r"#items:a/2$"))
    landed("a", 2)

    page.locator("#top").scroll_into_view_if_needed()
    page.locator("#jump button").click()
    page.wait_for_url(re.compile(r"#items:b/1$"))
    expect(part("b", 1)).to_be_focused()
    # A reload keeps the browser's restored offset, over the item the URL names.
    page.reload()
    expect(part("b", 1)).to_be_in_viewport()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_across_root_tabs_draws_the_key_the_entry_names(request, serve, engine):
    """A root tab set takes Back to an entry in another of its views and opens that
    view; the widget inside it still draws the item the entry's key names, though the
    user picked another item before leaving the view."""
    url = live_url(
        serve(
            leaf_page(
                "Items in tabs",
                '<lf-tabs id="views"><lf-tab id="first" label="First">'
                '<p><a id="to-part" href="#items:b/3">Part 3 of item b</a></p>'
                '<lf-items id="items"></lf-items><div style="height:1600px"></div>'
                '</lf-tab><lf-tab id="second" label="Second"><p>Elsewhere.</p>'
                "</lf-tab></lf-tabs>",
            ),
            layer_registry=ITEMS_LAYER,
            layer_widgets=ITEMS_WIDGETS,
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    b3 = page.locator('#items [data-item="b"][data-part="3"]')
    page.locator("#to-part").click()
    expect(b3).to_be_in_viewport()
    # The user picks another item inside the widget, which leaves the URL alone.
    page.locator("#items").evaluate("items => items.lfRevealDatum('a/1')")
    expect(b3).to_have_count(0)
    page.locator("#views").get_by_role("tab", name="Second", exact=True).click()
    page.wait_for_url(re.compile(r"#second$"))

    page.go_back()
    page.wait_for_url(re.compile(r"#items:b/3$"))
    expect(b3).to_be_in_viewport()


@pytest.mark.parametrize(
    ("route", "large", "focusable"),
    [("click", False, True), ("Tab", False, True), ("click", True, False)],
)
def test_back_returns_the_passage_chosen_between_trips(
    browser, serve, route, large, focusable
):
    """A passage the user chose after one trip, by click or Tab, is where the next trip
    departs from, even while the first landing still shows: Back returns to it, and
    another Back to the original reading. A click on words that take no focus is
    returned as the selection it left. The large landing's paragraph follows its
    section, since a click on the commented section opens its thread instead."""
    stop = ' tabindex="0"' if focusable else ""
    elsewhere = f'<p id="elsewhere"{stop}>This independent paragraph has no thread.</p>'
    first = (
        '<section id="first"><p>The first discussion concerns the importer.</p>'
        f'<div style="height:1800px"></div></section>{elsewhere}'
        if large
        else f'<p id="first">The first discussion concerns the importer.</p>{elsewhere}'
    )
    url = serve(
        leaf_page(
            "A fresh reading stop",
            "<h1>Reading before the conversations</h1>"
            '<p id="origin" tabindex="0">The reading before the thread walk.</p>'
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
        page.locator(f'.lf-margin-preview [data-lf-thread="{roots[0]}"]')
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
    second = page.locator(f'.lf-margin-preview [data-lf-thread="{roots[1]}"]')
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
        "document.activeElement.closest('[data-lf-thread]')?.dataset.lfThread === id",
        arg=roots[1],
    )
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    page.wait_for_function("top => Math.abs(scrollY-top) <= 2", arg=chosen_top)
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(page.locator("#origin")).to_be_focused()
    page.wait_for_function("scrollY < 100")


def test_a_reading_finds_words_drawn_outside_their_blocks_box(browser, serve):
    """A block whose own box lies below the window can still draw words in it, through a
    positioned child. A reading of the screen passes over a block only when its words
    are drawn inside its box, so the words the reader sees name the place, including
    once a breakpoint moves the child after an earlier reading, with no change to the
    page's text."""
    source = leaf_page(
        "Words outside their block",
        "<style>@media (width < 800px) {"
        " #drawn { position: absolute; top: 200px; left: 0 } }</style>"
        '<div style="position: relative">'
        '<div style="height: 1400px"></div>'
        '<p id="carrier">The carrier paragraph sits far below the window.'
        '<span id="drawn">These positioned words are drawn in the window.</span></p>'
        "</div>"
        + "".join(f"<p>Later paragraph {n} below the carrier.</p>" for n in range(5)),
    )
    page = open_page(browser, serve(source))
    resized(page, 1000, 600)
    rendered(page)
    reading = """async () => {
      const rp = await window.__lfCheckApi();
      return rp.readingBlock()?.id ?? null;
    }"""
    assert page.evaluate(reading) is None
    resized(page, 700, 600)
    rendered(page)
    assert page.evaluate(reading) == "carrier"


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
    expect(
        page.locator(f'.lf-margin-preview [data-lf-thread="{root}"]')
    ).to_be_focused()
    scroll_settled(page)
    page.go_back()
    page.wait_for_function("top => Math.abs(scrollY-top) <= 2", arg=chosen_scroll)
    returned = page.evaluate(reading)
    assert returned["place"]["quote"] == visible
    assert returned["top"] == pytest.approx(chosen["top"], abs=2)


def test_reading_place_names_a_projected_datum(browser, serve, subtests):
    """A paragraph's later words cannot precede the datum that splits its reading, and a
    long text block's row identity survives capture, serialization and reflow."""
    record = (
        "The projected record is the first visible passage the reader should keep. "
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Projected reading places",
                '<section id="source"><p id="paragraph">'
                '<span style="display:block;height:1100px">Earlier paragraph words.</span>'
                '<span id="record" style="display:block">'
                + record
                * 4
                + '</span><span style="display:block">'
                "The later continuation follows the record and must not take its place."
                '</span></p></section><div style="height:900px"></div>'
                '<pre id="rows">'
                + "".join(
                    f'<span id="row-{n}" style="display:block">'
                    "The same words occur on every independently addressed row.</span>"
                    for n in range(80)
                )
                + '</pre><div style="height:900px"></div>',
            )
        ),
    )

    with subtests.test(case="a passage inside a paragraph"):
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

    with subtests.test(case="a row among repeated words"):
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
    """Each step of the obligation walk somewhere else adds a history entry where the user
    stood, as each trip to a thread does, so Back returns to the obligation the user was
    on, though answering it took it out of On Me, and then to where they were reading.
    `m` from a thread `t` reached comes back to the thread, its card open again beside
    its passage."""
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

    def entry():
        return page.evaluate("navigation.currentEntry.index")

    def back_to(top):
        page.wait_for_function("navigation.transition === null")
        page.go_back()
        page.wait_for_function(
            "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=top
        )

    # `t` travels to the thread just below the first obligation, and `m` from there to
    # the second leaves that thread, so it adds an entry of its own: Back returns to the
    # thread's landing, its card open beside the passage again, and Back again to the
    # bottom.
    card = page.locator(".lf-margin-thread .lf-page-thread")
    start = entry()
    page.keyboard.press("t")
    page.wait_for_function("() => document.activeElement?.closest('[data-lf-thread]')")
    scroll_settled(page)
    thread = page.evaluate("document.scrollingElement.scrollTop")
    assert thread < reading - 1000
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    expect(card).to_be_hidden()
    scroll_settled(page)
    assert entry() == start + 2
    back_to(thread)
    expect(page.locator("#above")).to_be_in_viewport()
    expect(card).to_be_visible()
    back_to(reading)

    # From the bottom again, the obligation walk upward.
    start = entry()
    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()
    # Focus precedes the outer scroll, so observe movement before waiting for rest.
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=reading
    )
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert entry() == start + 1

    # Answering the obligation takes it out of On Me, so no walk's Shift reaches it again.
    page.keyboard.press("1")
    expect(page.locator("#se-rota[chosen]")).to_have_count(1)
    page.keyboard.press("Shift+m")
    expect(page.locator("#first-decision")).to_be_focused()
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=landed
    )
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked < landed - 1000
    assert entry() == start + 2
    back_to(landed)
    page.wait_for_function("() => document.activeElement?.closest('#second-decision')")
    back_to(reading)


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
    press_visible(page, panel_control(page, ALIGN_ROW, at="navigate"), touch=True)
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


def test_align_in_the_panel_stays_there_without_travel(browser, serve, subtests):
    """`g z` on a row in Threads, or on a control of an obligation in a reply the panel
    draws, moves nothing on the page and adds no history: the item it aligns is the panel's
    own."""
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
    travel = "[scrollY,history.length,navigation.currentEntry.key,location.href]"

    with subtests.test(case="a row in Threads"):
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        panel_settled(page, view="threads")
        row = page.locator(".lf-fp-thread").nth(4)
        row.focus()
        rendered(page)
        before = page.evaluate(travel)
        page.keyboard.press("g")
        page.keyboard.press("z")
        rendered(page)
        expect(row).to_be_focused()
        panel_settled(page, view="threads")
        assert page.evaluate(travel) == before

    with subtests.test(case="an obligation in a reply"):
        view = open_panel_thread(page, roots[4])
        control = view.locator('lf-option[id="reply-yes"]').get_by_role("checkbox")
        control.focus()
        before = page.evaluate(travel)
        page.keyboard.press("g")
        page.keyboard.press("z")
        rendered(page)
        expect(control).to_be_focused()
        assert page.evaluate(travel) == before


def test_a_nearest_landing_asks_whether_its_box_is_already_shown(
    browser, serve, subtests
):
    """Every nearest landing first asks whether its box is already shown, which it is
    where the landing would move nothing: all of it in view where it fits its room, and
    filling the room where it is longer. Each case stands in a part of the page of its
    own and scrolls to it first, so the cases share one page.

    A box taller than the window that shows only in part still comes in as far as it
    fits, its opening at the band's top, and is then shown. A wrapper clipping only
    sideways bounds no height, so an editor standing in an `overflow-x: clip` row 20px
    tall still fits, and 30px of it in view is not yet shown.

    The room a box has is what a landing could give it, not what the boxes around it
    show where they stand now: a 250px box a 300px pane holds whole, the pane's foot
    below the window, fits the pane, so it is not yet shown, and a nearest landing
    brings the page up until all of it is.

    A 300px box 100px down a 250px pane that stands 100px above the band shows 150px of
    itself. A nearest landing scrolls the pane 100px to show 250px, and the page back
    100px to keep the pane's top in the band, so the box stands where it stood: the two
    moves cancel on screen but not in what the user sees, so it is not yet shown, and
    the landing makes both.

    A fixed box stands still while every box around it scrolls, so a landing on one the
    window doesn't show, as a Tab's arrival makes, moves none of them. A fixed box a
    transformed box holds is placed in that box, not the window, so it rides the page's
    scroll and a landing scrolls the page to show it."""
    source = leaf_page(
        "Room",
        '<button id="fixed" style="position:fixed;left:20px;top:1200px">Fixed</button>'
        '<div style="height:100px"></div><div style="transform:translateZ(0)">'
        '<button id="carried" style="position:fixed;left:20px;top:1300px">Carried'
        '</button></div><div style="height:2000px"></div>'
        '<div style="overflow-x:clip;height:20px"><div id="box" style="height:100px"></div></div>'
        '<div style="height:2000px"></div><div id="tall" style="height:5000px"></div>'
        '<div style="height:1200px"></div>'
        '<div id="pane" style="height:300px;overflow:auto">'
        '<div id="whole" style="height:250px"></div><div style="height:600px"></div>'
        '</div><div style="height:1600px"></div>'
        '<div id="short-pane" style="height:250px;overflow:auto">'
        '<div style="height:100px"></div><div id="long" style="height:300px"></div>'
        '<div style="height:600px"></div></div><div style="height:1600px"></div>',
    )
    page = open_page(browser, serve(source))
    page.set_viewport_size({"width": 1280, "height": 900})

    with subtests.test(case="a fixed box"):
        assert (
            page.evaluate("""async () => {
              const {scrollIntoView} = await window.__lfWidgetApi();
              scrollTo({top: 100, behavior: 'instant'});
              const fixed = document.querySelector('#fixed');
              scrollIntoView(fixed, {block: 'nearest', behavior: 'instant'});
              return scrollY;
            }""")
            == 100
        )

    with subtests.test(case="a fixed box a transformed box holds"):
        reading = page.evaluate("""async () => {
          const {landingBand, seenRect} = await window.__lfCheckApi();
          const {scrollIntoView} = await window.__lfWidgetApi();
          scrollTo({top: 0, behavior: 'instant'});
          const carried = document.querySelector('#carried');
          const before = carried.getBoundingClientRect().top;
          scrollIntoView(carried, {block: 'nearest', behavior: 'instant'});
          const box = carried.getBoundingClientRect();
          return {before, bottom: box.bottom, y: scrollY, seen: Boolean(seenRect(carried, new Map())),
                  band: landingBand(document.scrollingElement).bottom};
        }""")
        assert reading["before"] > 900, reading
        assert reading["y"] > 0, reading
        assert reading["seen"], reading
        assert reading["bottom"] <= reading["band"] + 1, reading

    with subtests.test(case="what the window shows"):
        reading = page.evaluate("""async () => {
          const {alreadyShown, fitsWhole, landingBand} = await window.__lfCheckApi();
          const {scrollIntoView, shownWindow} = await window.__lfWidgetApi();
          const partly = (node) => {
            const top = node.getBoundingClientRect().top - (shownWindow().bottom - 30);
            scrollBy({top, behavior: 'instant'});
            return [fitsWhole(node), alreadyShown(node)];
          };
          const tall = document.querySelector('#tall');
          const readings = [partly(document.querySelector('#box')), partly(tall)];
          scrollIntoView(tall, {block: 'nearest', behavior: 'instant'});
          return {readings, landed: alreadyShown(tall),
                  top: tall.getBoundingClientRect().top,
                  band: landingBand(document.scrollingElement).top};
        }""")
        assert reading["readings"] == [[True, False], [False, False]], reading
        assert reading["landed"], reading
        assert reading["top"] == pytest.approx(reading["band"], abs=1), reading

    with subtests.test(case="a box whole in a pane below the window"):
        reading = page.evaluate("""async () => {
          const {alreadyShown, landingBand} = await window.__lfCheckApi();
          const {scrollIntoView} = await window.__lfWidgetApi();
          const pane = document.querySelector('#pane');
          const box = document.querySelector('#whole');
          scrollBy({top: pane.getBoundingClientRect().top - (innerHeight - 200),
                    behavior: 'instant'});
          const before = {shown: alreadyShown(box), bottom: box.getBoundingClientRect().bottom};
          scrollIntoView(box, {block: 'nearest', behavior: 'instant'});
          return {before, after: alreadyShown(box), bottom: box.getBoundingClientRect().bottom,
                  band: landingBand(document.scrollingElement).bottom};
        }""")
        assert reading["before"]["bottom"] > reading["band"], reading
        assert reading["before"]["shown"] is False, reading
        assert reading["bottom"] <= reading["band"] + 1, reading
        assert reading["after"] is True, reading

    with subtests.test(case="a box longer than its pane"):
        reading = page.evaluate("""async () => {
          const {alreadyShown, landingBand, seenRect} = await window.__lfCheckApi();
          const {scrollIntoView} = await window.__lfWidgetApi();
          const pane = document.querySelector('#short-pane');
          const box = document.querySelector('#long');
          const band = landingBand(document.scrollingElement).top;
          scrollBy({top: pane.getBoundingClientRect().top - (band - 100), behavior: 'instant'});
          const seenHeight = () => {
            const seen = seenRect(box, new Map());
            return seen ? Math.round(seen.bottom - seen.top) : 0;
          };
          const before = {shown: alreadyShown(box), seen: seenHeight(),
                          top: Math.round(box.getBoundingClientRect().top)};
          scrollIntoView(box, {block: 'nearest', behavior: 'instant'});
          return {before, pane: pane.scrollTop, seen: seenHeight(),
                  top: Math.round(box.getBoundingClientRect().top), after: alreadyShown(box)};
        }""")
        assert reading["before"]["seen"] == 150, reading
        assert reading["before"]["shown"] is False, reading
        assert reading["pane"] == 100, reading
        assert reading["seen"] == 250, reading
        assert reading["top"] == reading["before"]["top"], reading
        assert reading["after"] is True, reading


def test_align_current_tall_block_in_a_pane_in_a_pane_lands_its_opening(browser, serve):
    """`g z` on a tall item in a pane that stands in another pane, both partly above the
    window, aligns the item's opening in its own pane and then brings that opening to
    the page's band: each box around reads where the boxes inside it have just put the
    item, so the opening is not left above the window. The press stays in the current
    history entry."""
    source = leaf_page(
        "A tall item two panes deep",
        '<h1>Read the opening</h1><div style="height:700px"></div>'
        '<div id="outer" data-bound="start" style="height:300px;overflow:auto">'
        '<div style="height:200px"></div>'
        '<div id="inner" data-bound="start" '
        'style="height:250px;overflow:auto;scroll-padding-top:24px">'
        '<pre id="tall" tabindex="0" style="margin:0">'
        + "A line in the current item.\n"
        * 80
        + '</pre><div style="height:600px"></div></div>'
        '<div style="height:1000px"></div></div><div style="height:3000px"></div>',
    )
    page = open_page(browser, serve(source))
    page.set_viewport_size({"width": 1440, "height": 900})
    page.emulate_media(reduced_motion="reduce")
    page.locator("#tall").evaluate("el => el.focus({preventScroll: true})")
    page.evaluate(
        """() => {
          const outer = document.querySelector('#outer');
          scrollTo({top: outer.getBoundingClientRect().top + scrollY + 100,
                    behavior: 'instant'});
          document.querySelector('#inner').scrollTop = 300;
        }"""
    )
    scroll_settled(page)
    assert page.locator("#tall").bounding_box()["y"] < 0
    history = page.evaluate("[history.length,navigation.currentEntry.key]")
    page.keyboard.press("g")
    page.keyboard.press("z")
    scroll_settled(page)
    _expect_aligned(page, "#tall")
    assert page.locator("#inner").evaluate("box => box.scrollTop") == 0
    expect(page.locator("#tall")).to_be_focused()
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
    page.evaluate(
        """async (block) => {
          const {scrollIntoView} = await window.__lfWidgetApi();
          const target = document.querySelector('#quarter-target');
          scrollIntoView(target, {block, behavior: 'instant'});
        }""",
        alignment,
    )
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
    # The menu took the On view's place, as its tab does, and the command puts it away.
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
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
    expect(page.locator(panel_view("versions"))).to_be_visible()
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
        '<h1>Review</h1><lf-diff id="patch" source="review-patch">'
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
        # The page's field wears `c` once the key has let go of the line scrolled away.
        expect(panel_field(page)).to_have_attribute(
            "placeholder",
            re.compile(r"^That selected passage is unavailable on this version"),
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
    browser, serve, subtests
):
    """A step that lands the user in the document moves the Tab starting point there, and
    closing a mode gives back the press that opened it with the user's place, whichever
    surface it is and however it closes: Threads, the reference, and the Page Map by
    Escape or by its Close. The page has not moved under it either.

    The landing is blurred, so `activeElement` reads `body` whether or not it moved, and
    every journey that asserts only that would pass over a landing that had quietly reset
    the user to the top of the page. The press that tells them apart is the Tab after
    it: from a panel opened four screens down, it belongs on from the words in front of
    the user rather than at the document's first stop.

    A user working from the page stands on `body`: `letGo` puts them there so Space and
    PageDown reach the document's own scroll box. `?` from there recorded `body` as the
    door and closing handed focus back to it, and focusing `body` resets the browser's
    sequential focus navigation starting point, so the next Tab began at the top of the
    document. Authored controls before and after the reading distinguish restarting at
    the top from carrying on where the user was. Each case starts from there:
    `RELEASE_FOCUS` puts the starting point back at the top, where a new page has it."""
    page = open_page(browser, serve(READING_CONTROLS_PAGE))
    threads = page.locator(panel_view("threads"))
    reference = page.locator(".lf-command-reference")
    page_map = page.get_by_role("dialog", name="Page Map", exact=True)

    def close_threads():
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        expect(threads).to_be_focused()
        page.keyboard.press("Escape")
        panel_settled(page, open=False)

    def close_reference():
        page.keyboard.press("?")
        expect(reference).to_be_visible()
        page.keyboard.press("Escape")
        expect(reference).to_be_hidden()

    def open_page_map():
        page.keyboard.press("g")
        page.keyboard.press("Shift+p")
        expect(page_map).to_be_visible()

    def close_page_map_by_escape():
        open_page_map()
        page.keyboard.press("Escape")
        expect(page_map).to_be_hidden()

    def close_page_map_by_its_close():
        open_page_map()
        page_map.get_by_role("button", name="Close Page Map").click()
        expect(page_map).to_be_hidden()

    for surface, close in (
        ("threads", close_threads),
        ("reference", close_reference),
        ("page map by Escape", close_page_map_by_escape),
        ("page map by its Close", close_page_map_by_its_close),
    ):
        with subtests.test(surface=surface):
            page.evaluate(RELEASE_FOCUS)
            page.evaluate("() => document.getElementById('p40').scrollIntoView()")
            page_at_rest(page)
            before = page.evaluate("() => document.scrollingElement.scrollTop")
            close()
            assert page.evaluate("() => document.activeElement === document.body")
            assert page.evaluate("() => document.scrollingElement.scrollTop") == before

            page.keyboard.press("Tab")
            expect(page.locator("#next-control")).to_be_focused()
            # And nothing of the borrow is left on the author's paragraph: `tabindex` is
            # not in PAGE_PAINT_ATTRIBUTES, so a stop left in place would be runtime paint
            # the replay signature has no vocabulary for.
            assert (
                page.evaluate(
                    "() => document.querySelectorAll('main [tabindex]').length"
                )
                == 0
            )
        # What a failed case left up goes before the next case opens its surface.
        page.keyboard.press("Escape")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_landing_that_moves_nothing_stops_a_scroll_still_under_way(
    engine, request, serve
):
    """A navigation takes the reader's place from a scroll the browser is still driving,
    even where its destination already stands where it lands: the log the reader set
    moving stops where the landing found it, rather than running on past what they
    chose. Firefox ran the log on to its end, since it stops no smooth scroll for an
    instant write of the position the page last saw (arrivals.js,
    `stopWhereItStands`)."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(3))
    rows = "".join(
        f"<p>Line {n} of the incident, long enough to read as its own passage.</p>"
        for n in range(200)
    )
    source = leaf_page(
        "Landing during a scroll",
        f'{filler}<h2 id="section"><span id="named">The section</span> the reader '
        f'landed on</h2><div id="log" data-bound="start" style="height: 400px">{rows}'
        f"</div>{filler * 20}",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1280, 800)
    page.evaluate("location.hash = 'section'")
    scroll_settled(page)
    rendered(page)
    page_top = page.evaluate("document.scrollingElement.scrollTop")
    # The log's smooth scroll is the browser's to drive; the landing on a name inside the
    # heading already in place asks nothing to move.
    started = page.evaluate(
        """async () => {
          const log = document.getElementById('log');
          log.scrollTo({top: log.scrollHeight, behavior: 'smooth'});
          const frame = () => new Promise(r => requestAnimationFrame(() => r()));
          while (log.scrollTop < 20) await frame();
          location.hash = 'named';
          return log.scrollTop;
        }"""
    )
    scroll_settled(page)
    rendered(page)
    after = page.evaluate(
        """() => {
          const log = document.getElementById('log');
          return {log: log.scrollTop, limit: log.scrollHeight - log.clientHeight,
                  page: document.scrollingElement.scrollTop};
        }"""
    )
    assert after["page"] == pytest.approx(page_top, abs=2), after
    assert after["log"] < started + 200 < after["limit"], (started, after)
