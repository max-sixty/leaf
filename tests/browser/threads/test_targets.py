"""What a thread stands on and how its card shows it: passage links, marks on widgets in
an agent's reply, and quotes of words the page has since rewritten."""

import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, response_reference
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import mark_point
from render_harness import (
    EXAMPLE_PACKAGES,
    RELEASE_FOCUS,
    any_owner_entry,
    cursor_at,
    expect_design_mode,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    select_words,
    selection_field,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import (
    CHANGE_PAGE,
    REPLY_CHANGE,
    append_agent_reply,
    open_panel_thread,
    seed_reply,
    thread_row,
)
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.records import page_data as page_data_model
from leaf.records import transaction as transaction_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD, choose_threads_in_panel

pytestmark = pytest.mark.shifts_unsurveyed


def open_from_threads(page, root):
    """Open the thread `root` from its row in the panel's Threads, as a reader finds it,
    and return what shows it: the panel's view, or its passage's margin card."""
    thread_row(page, root).click()
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    margin = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
    )
    expect(view.or_(margin).filter(visible=True).first).to_be_visible()
    rendered(page)
    if view.filter(visible=True).count():
        # A painted view can still be moving; later tests read its touch reach.
        panel_settled(page, view="thread")
    return view if view.filter(visible=True).count() else margin


def test_a_thread_mark_inside_a_tab_panel_opens_on_press(browser, serve):
    source = leaf_page(
        "Thread in tabs",
        '<lf-tabs id="views">'
        '<lf-tab id="first" label="First">'
        '<p id="inside">Commented words in the first tab.</p>'
        '</lf-tab><lf-tab id="second" label="Second">Other words.</lf-tab>'
        "</lf-tabs>",
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "id": "inside-thread",
                    "author": "user",
                    "revision": 1,
                    "text": "About this paragraph.",
                    "anchor": {"section": "inside", "quote": "Commented words"},
                }
            ],
        ),
    )
    panel = page.locator("#first")
    expect(panel).to_have_attribute("tabindex", "0")
    passage = page.locator("#inside")
    at = mark_point(page, "lf-mark")
    page.mouse.move(*at)
    expect(passage).to_have_css("cursor", "pointer")
    page.mouse.click(*at)
    expect(
        page.locator(
            '.lf-margin-preview .lf-page-thread[data-lf-thread="inside-thread"]'
        )
    ).to_be_visible()


def test_an_armed_button_keeps_its_cursor_whether_or_not_a_thread_marks_it(
    browser, serve
):
    """Holding ⌥, a press is the aim's, and a button a thread is on keeps the cursor its
    unmarked twin shows."""
    source = leaf_page(
        "Commented button",
        '<p><button id="act">Act</button> <button id="twin">Twin</button></p>',
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "id": "act-thread",
                    "author": "user",
                    "revision": 1,
                    "text": "About this button.",
                    "anchor": {"section": "act"},
                },
            ],
        ),
    )
    expect(page.locator("#act")).to_have_class(re.compile(r"\blf-mark-el\b"))
    armed = {}
    for button in ("twin", "act"):
        page.locator(f"#{button}").hover()
        page.keyboard.down("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_id(button)
        armed[button] = page.locator(f"#{button}").evaluate(
            "el => getComputedStyle(el).cursor"
        )
        page.keyboard.up("Alt")
    assert armed["act"] == armed["twin"], armed


def test_a_press_a_widget_takes_opens_no_thread_marked_over_it(browser, serve):
    """A press means one thing. A press on an option card's marked words picks the
    option and one on a gloss's pins its card, so neither opens the thread on those
    words, whose reply box would take the user's focus (annotations/composing/surface.js,
    the page's click). A gloss in a label leaves the press to the label, which ticks its
    box. A press on marked words outside any control still opens their thread."""
    source = leaf_page(
        "Commented question",
        '<lf-group id="cache-q" label="Which cache should the importer use?">'
        "<h2>Which cache should the importer use?</h2>"
        '<p id="words">Both hold a day of results.</p>'
        '<p>Only a <lf-gloss id="durable">durable store<span popover>It survives a '
        "restart.</span></lf-gloss> keeps them.</p>"
        '<p><label><input type="checkbox" id="wal-on"> Turn on the '
        '<lf-gloss id="wal">WAL<span popover>A log of each write before it lands.'
        "</span></lf-gloss>"
        "</label></p>"
        '<lf-options id="cache">'
        '<lf-option id="cache-memory" label="In memory"><strong>In memory</strong>'
        " Nothing new to run.</lf-option>"
        '<lf-option id="cache-redis" label="Redis"><strong>Redis</strong>'
        " One more service.</lf-option>"
        "</lf-options></lf-group>",
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": f"About {quote}?",
                    "anchor": {"section": "cache-q", "quote": quote},
                }
                for quote in (
                    "Redis",
                    "durable store",
                    "WAL",
                    "Both hold a day of results.",
                )
            ],
        ),
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 4")
    card = page.locator(".lf-margin-preview")

    page.locator("#cache-redis strong").click()
    expect(page.locator("#cache-redis .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    page.locator("#wal").click()
    expect(page.locator("#wal-on")).to_be_checked()
    expect(page.locator("#wal [aria-expanded]")).to_have_attribute(
        "aria-expanded", "false"
    )
    page.locator("#durable").click()
    expect(page.locator("#durable [aria-expanded]")).to_have_attribute(
        "aria-expanded", "true"
    )
    rendered(page)
    expect(card).to_be_hidden()

    words = page.locator("#words")
    words.click(position={"x": 12, "y": words.bounding_box()["height"] / 2})
    expect(card.locator("leaf-text")).to_be_focused()


def test_a_thread_on_words_a_widget_renders_stands_where_the_widget_does(
    browser, serve
):
    """A widget may render the page's words into a declared shadow tree, and a passage
    inside one is placed inside that tree. Asked to compare it with an element of the
    document, `compareDocumentPosition` answers "disconnected" in an order of its own
    choosing, and `contains` answers no across the same boundary — so the thread would
    sort and group by something the user has never seen.

    The host is the element the page holds, and where the page holds it is where those
    words are. So the thread reads after the paragraphs above the widget and before
    the ones below it. The `t` walk reads the page's order (Threads lists the newest
    first), so the walk from the page's top steps through the three in that order."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    # A passage in a projected datum is anchored on its datum, as capture writes it.
    patch = panel_comment(
        d,
        "Twelve is arbitrary.",
        {
            "section": "how-patch",
            "datum": '["gateway/limits.py","new",2]',
            "quote": "the ceiling doubles per approval",
        },
    )
    both = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page = open_page(browser, url)
    # The passage really is inside the widget's shadow tree, so the reading under test is
    # the cross-tree one rather than an ordinary document comparison.
    assert page.evaluate(
        """() => {
             const root = document.getElementById('how-patch').shadowRoot;
             return Boolean(root) && [...(CSS.highlights.get('lf-mark') ?? [])]
               .some((r) => root.contains(r.startContainer));
           }"""
    ), "the fixture's passage is not marked inside a shadow tree"
    for thread in (lede, patch, both):
        page.keyboard.press("t")
        # A thread on the diff's words opens in the diff, the others in the margin.
        expect(
            page.locator(f'.lf-page-thread[data-lf-thread="{thread}"]')
        ).to_be_focused()


# A page long enough to hold a reading position worth losing, and a change to decide
# in each document, so every reading below has the same widget in both places.
REPLY_TRAVEL_PAGE = leaf_page(
    "travel",
    "<h1 id='tv-h'>Session store</h1>"
    + "".join(
        f"<p id='tv-p{n}'>Paragraph {n}. "
        + "Words enough to wrap the column. " * 8
        + "</p>"
        for n in range(40)
    ),
)


ARMED_PAGE = leaf_page(
    "Armed cursors",
    '<section id="items"><p id="item">Words in an item.</p>'
    '<p id="marked">Words in a marked item.</p>'
    '<p id="stops">A marked item holding <span id="stop" tabindex="0">a tab stop'
    "</span> beside its words.</p>"
    '<p id="passage">Words around <span class="quoted">a marked passage</span> in an'
    " item.</p>"
    '<p id="drafted">Words a draft will stand on.</p>'
    '<p id="helped">Words in an item that states its own cursor.</p>'
    '<p id="links"><a id="link" href="#items">A link in an item</a></p></section>',
    head="<style>#items #helped { cursor: help; }</style>",
)
# The cursor the user sees at each place, at rest, holding ⌥, and in Design mode
# (chrome.css, annotation-chrome.css).
ARMED_CURSORS = {
    "words in an item": ("auto", "pointer", "pointer"),
    "beside the column": ("auto", "auto", "auto"),
    "words in a marked item": ("auto", "pointer", "pointer"),
    "a tab stop in a marked item": ("auto", "auto", "auto"),
    "a marked passage": ("pointer", "pointer", "pointer"),
    "a link in an item": ("pointer", "pointer", "pointer"),
    "an item that states its own cursor": ("help", "pointer", "pointer"),
}


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_armed_page_shows_each_place_the_cursor_its_press_keeps(
    request, serve, engine
):
    """A hand promises a press: at rest, where a press opens a thread, on a passage's
    marked words; holding ⌥ or in Design mode, where the aim's press takes an item. A
    control keeps its own cursor in either, even among marked words, where a press only
    focuses or works it; so do the words of an item a thread is on as a whole, which a
    press at rest leaves alone (annotations/anchor-paint.js, header), the words no item
    holds, a draft's item at rest, and a mark in the chrome, which neither press takes. Where the aim's press takes an item, its hand covers any cursor the page
    gives the item. Each place's cursor is read where the pointer is, since each hand is
    painted on the element under it (annotations/anchor-paint.js, panel/page-geometry.js); a mark of the
    arm on `body` made Firefox visit every element of the page as ⌥ went down or up."""
    url = serve(
        ARMED_PAGE,
        events=[
            {
                "kind": "comment",
                "id": f"on-{section}",
                "author": "user",
                "revision": 1,
                "text": "About this.",
                "anchor": anchor,
            }
            for section, anchor in (
                ("marked", {"section": "marked"}),
                ("stops", {"section": "stops", "quote": "holding a tab stop beside"}),
                ("passage", {"section": "passage", "quote": "a marked passage"}),
            )
        ],
    )
    seed_reply(
        serve.page_dir,
        '<lf-group id="tv-decision-region" label="Which store should I write up?">\n<h3 id="tv-decision-region-h">Which store should I write up?</h3>'
        '<lf-options id="tv-decision">'
        '<lf-option id="tv-redis">Redis</lf-option>'
        "</lf-options></lf-group>",
        "tv-decision-region",
    )
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1280, 900)
    rendered(page)

    def middle(selector, x=None):
        box = page.locator(selector).first.bounding_box()
        return (
            box["x"] + (box["width"] / 2 if x is None else x),
            box["y"] + box["height"] / 2,
        )

    places = {
        "words in an item": middle("#item", 20),
        "beside the column": (40, middle("#item")[1]),
        "words in a marked item": middle("#marked", 20),
        "a tab stop in a marked item": middle("#stop"),
        "a marked passage": middle("#passage .quoted"),
        "a link in an item": middle("#link"),
        "an item that states its own cursor": middle("#helped", 20),
    }

    def seen(point):
        page.mouse.move(*point)
        rendered(page)
        return cursor_at(page, *point)

    found = {name: [seen(point)] for name, point in places.items()}
    for name, point in places.items():
        page.mouse.move(*point)
        page.keyboard.down("Alt")
        found[name].append(seen(point))
        page.keyboard.up("Alt")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("l")
    expect_design_mode(page)
    for name, point in places.items():
        found[name].append(seen(point))
    # The mode's own key leaves it. Escape would first put away a preview the readings
    # left standing, as a slow machine's rest on the link does
    # (browser/runtime/dom/keyboard/AGENTS.md, "Escape").
    page.keyboard.press("l")
    expect_design_mode(page, on=False)
    assert {name: tuple(each) for name, each in found.items()} == ARMED_CURSORS

    # A draft's item: the draft's own cursor at rest, and the aim's hand armed.
    drafted = middle("#drafted", 20)
    page.mouse.move(*drafted)
    page.keyboard.down("Alt")
    page.mouse.click(*drafted)
    page.keyboard.up("Alt")
    expect(page.locator("#drafted")).to_have_class(re.compile(r"\blf-pending\b"))
    draft = [seen(drafted)]
    page.keyboard.down("Alt")
    draft.append(seen(drafted))
    page.keyboard.up("Alt")
    assert draft == ["auto", "pointer"], draft
    page.keyboard.press("Escape")

    # A mark in the chrome keeps its own cursor, armed, in Design mode or neither.
    open_panel_thread(page, "tv-decisioned")
    rendered(page)
    expect(page.locator(".lf-fp-view #tv-decision-region")).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    heading = middle(".lf-fp-view #tv-decision-region h3", 20)
    chrome = [seen(heading)]
    page.keyboard.down("Alt")
    chrome.append(seen(heading))
    page.keyboard.up("Alt")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("l")
    expect_design_mode(page)
    chrome.append(seen(heading))
    assert chrome == ["auto", "auto", "auto"], chrome


def test_a_control_in_a_reply_holds_the_page_s_control_shape(browser, serve):
    """A change sent in a reply keeps the canonical circular control.

    A reply is upgraded inside a closed comment panel, where its box is zero, and its
    controls, measured there, would collapse. The control's circle is fixed,
    so it is the same shape in the reply as on the page.

    The page's own change is the geometry reference."""
    reply_url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(serve.page_dir, REPLY_CHANGE, "tv-msg-sug")
    page = open_page(browser, reply_url)
    resized(page, 1280, 900)
    open_panel_thread(page, "tv-decisioned")
    geometries = (
        "() => [...document.querySelectorAll("
        f"'.lf-margin-entry{any_owner_entry('suggestion')}')]"
        ".map((b) => { const s = getComputedStyle(b); "
        "return [s.width, s.height, s.borderRadius]; })"
    )
    in_reply = page.evaluate(geometries)
    assert in_reply and all(shape == ["32px", "32px", "6px"] for shape in in_reply), (
        f"a control in a reply lost the margin entry face: {in_reply}"
    )
    page.close()

    # The same controls on the page, whose numbers these have to be.
    page = open_page(browser, serve(CHANGE_PAGE))
    resized(page, 1280, 900)
    on_page = page.evaluate(geometries)
    assert in_reply == on_page, (
        f"the same control measures {in_reply} in a reply and {on_page} on the page"
    )


def test_a_thread_on_a_widget_its_reply_brings_is_marked_as_the_reply_lands(
    browser, serve
):
    """A target the panel's preparation materializes is painted in the same pass.

    The reply carrying a widget and a thread anchored on that widget arrive in one
    reading. The thread presenter reads its targets before the panel prepares the
    reply, when the widget is not yet in the document, so only its reading after the
    panel commits finds the target; no later publication comes to paint it."""
    url = serve(REPLY_TRAVEL_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-decisioned",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, "tv-decisioned")
    expect(page.locator(".lf-fp-view #tv-decision")).to_have_count(0)
    # Whether the widget is marked in the first frame that shows it. A later
    # publication, such as the page's own bookkeeping, repaints the targets again and
    # would hide a pass that left it bare.
    page.evaluate("""() => {
      window.markedOnArrival = new Promise((resolve) => {
        const look = () => {
          const widget = document.querySelector('.lf-fp-view #tv-decision');
          if (widget) resolve(widget.classList.contains('lf-mark-el'));
          else requestAnimationFrame(look);
        };
        requestAnimationFrame(look);
      });
    }""")

    # One transaction, so the page reads both records in one state answer.
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        for event in (
            {
                "kind": "reply",
                "author": "agent",
                "parent": "tv-decisioned",
                "revision": 1,
                "text": "Depends what you want to keep:\n\n"
                '<lf-options id="tv-decision">'
                '<lf-option id="tv-redis">Redis</lf-option></lf-options>',
            },
            {
                "kind": "comment",
                "id": "tv-on-it",
                "author": "user",
                "revision": 1,
                "text": "Redis, and say why in the patch.",
                "anchor": {"section": "tv-decision"},
            },
        ):
            transaction._append_record({"attention": True, **event})

    assert page.evaluate("() => window.markedOnArrival"), (
        "the widget the reply brought showed unmarked, though a thread stands on it"
    )
    expect(thread_row(page, "tv-on-it")).to_have_count(1)


def test_a_target_a_reply_widget_redraws_keeps_its_mark(browser, serve):
    """A widget in a reply that replaces a part another thread stands on, and says its
    layout changed, has the replacement marked.

    The reply's markup is authored content, though it stands in the runtime's panel, so
    its layout signal asks for the thread pass that finds the new node. A signal from
    the panel's own cards asks for none."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-decision"><lf-option id="tv-redis">Redis</lf-option>'
        '<lf-option id="tv-cookie">A signed cookie</lf-option></lf-options>',
        "tv-redis",
    )
    page = open_page(browser, url)
    open_panel_thread(page, "tv-decisioned")
    marked = re.compile(r"\blf-mark-el\b")
    expect(page.locator(".lf-fp-view #tv-redis")).to_have_class(marked)

    # Read once the pass the signal asked for has painted, and before anything else
    # (the clock's next tick) would paint the targets again.
    remarked = page.evaluate("""async () => {
      const { whenDocumentPresented } = await window.__lfCheckApi();
      const old = document.querySelector('.lf-fp-view #tv-redis');
      const replacement = old.cloneNode(true);
      replacement.classList.remove('lf-mark-el');
      old.replaceWith(replacement);
      await document.querySelector('.lf-fp-view #tv-decision').dispatchEvent(new CustomEvent('lf-layout', { bubbles: true, composed: true }));
      await whenDocumentPresented();
      await new Promise((resolve) => requestAnimationFrame(() => resolve()));
      return replacement.classList.contains('lf-mark-el');
    }""")
    assert remarked, (
        "the part the reply widget redrew lost the mark its thread gives it"
    )


def test_a_boxless_widget_in_a_reply_still_shows_the_parts_it_paints(browser, serve):
    """A wrapper that generates no box shows as what its contents paint — in either
    document.

    `shownParts` falls back to an element's children when the element itself has no
    box, which is what a mark hangs on and what a decision's ring hangs on. Keeping the
    runtime's own apparatus out of that fallback by asking whether each child is under
    the runtime's chrome would filter away every child of a widget an agent sent in a
    reply, which is: the panel over it answers for every child, so the widget would
    show as nothing at all. Bounded at the widget, the panel above it is not its own
    apparatus and the parts show.

    `display: contents` on a widget is a page's line to write — the shipped vocabulary
    has none today, and `shownParts` exists because any layer can. A widget in a reply
    stands in the chrome, so the page's rule names it there, which outweighs the chrome's
    guard against light page rules (styles/chrome-guard.css)."""
    page_source = REPLY_TRAVEL_PAGE.replace(
        "</head>",
        "<style>.lf-chrome lf-options { display: contents }</style>\n</head>",
    )
    url = serve(page_source, packages=EXAMPLE_PACKAGES)
    # The page's unlayered style puts a group's wrapper in `contents`; the
    # subject is the boxless wrapper fallback, not package-theme precedence.
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-decision">'
        '<lf-option id="tv-redis" selected>Redis</lf-option>'
        "</lf-options>",
        "tv-decision",
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    open_panel_thread(page, "tv-decisioned")
    parts = page.evaluate(
        """async () => {
             const { shownParts } = await window.__lfCheckApi();
             const el = document.querySelector('.lf-fp-view #tv-decision');
             return { boxless: el.getBoundingClientRect().height === 0,
                      display: getComputedStyle(el).display,
                      parts: shownParts(el).map((p) => p.id || p.localName) };
           }"""
    )
    assert parts["boxless"], (
        f"the widget draws as {parts['display']!r}, so it has a box of its own and "
        "the fallback below was never reached — the project layer's rule lost to one "
        "the shipped theme states at a weight a bare tag selector cannot reach"
    )
    assert parts["parts"], (
        "a widget an agent sent shows as nothing: no box of its own, and every part "
        "its contents paint read as the panel's apparatus"
    )


def test_a_thread_on_a_rewrite_is_named_by_its_old_and_new_words(browser, serve):
    """A rewrite's slots are two words apart on the page and no characters apart in
    the text, so a thread anchored on one would be quoted as "redblue". The module that
    names its own kind (`lfWord`) names its own words the same way (`lfSays`)."""
    url = serve(
        leaf_page(
            "rewrite",
            '<p id="p">The wall is <lf-suggestion id="swap">'
            "<lf-old>red</lf-old><lf-new>blue</lf-new></lf-suggestion> now.</p>",
        )
    )
    root = panel_comment(serve.page_dir, "Neither.", {"section": "swap"})
    page = open_page(browser, url)
    expect(open_from_threads(page, root).locator(".lf-quote-label")).to_have_text(
        "§ rewrite · red → blue"
    )


def test_a_whole_item_s_comment_stays_on_the_item_a_revision_rewords(browser, serve):
    """A triple-click on a list item, in Chromium, ends the selection at the next
    item's start, so the range's common ancestor is the list. The comment names the item
    its words stand in, so a revision that rewords the item leaves the thread on that
    item rather than on the whole list."""
    item = (
        '<li id="item-54"><strong>#54 A faster line.</strong> Nine idle messages.</li>'
    )
    source = leaf_page(
        "open items",
        '<ul id="open-items">'
        '<li id="item-53"><strong>#53 An earlier item.</strong> It stays.</li>'
        + item
        + '<li id="item-59"><strong>#59 A fork in Codex.</strong> Later.</li></ul>',
    )
    url = serve(source)
    page = open_page(browser, live_url(url))
    select_words(page, "#item-54")
    write(page.locator(".lf-composer leaf-text"), "sure, check this out")
    with sending(page, "the comment on a whole item"):
        page.locator(".lf-composer button.lf-compose-submit").click()
    told(page)
    d = serve.page_dir
    root = next(e for e in events_model.read_events(d) if e["kind"] == "comment")
    assert root["anchor"]["section"] == "item-54"
    stamp_page(
        d,
        source.replace(
            item, '<li id="item-54"><strong>#54 Why six forks.</strong></li>'
        ),
        "Reworded #54",
    )
    wait_for_revision(page, 2)
    moved = next(e for e in events_model.read_events(d) if e["kind"] == "reanchor")
    assert moved["anchor"] == {"section": "item-54"}


@pytest.mark.parametrize(
    ("removed", "touch"),
    [(True, False), (False, False), (True, True)],
    ids=["detached-keyboard", "rewritten-keyboard", "detached-touch"],
)
def test_original_quoted_words_remain_readable_after_the_page_rewrites_them(
    browser, serve, removed, touch
):
    """A compact quotation cannot borrow its full reading from words no longer there."""
    old = (
        "The earlier plan keeps the conversation beside the selected passage. " * 12
    ) + "FINAL IMPORTANT WORDS: manual review before release."
    section = (
        '<section id="plan"><h2>Earlier plan</h2><p id="passage">'
        + old
        + "</p></section>"
    )
    source = leaf_page(
        "Retained quotation", '<h1 id="title">Release plan</h1>' + section
    )
    url = serve(source)
    context = browser.new_context(
        viewport={"width": 390 if touch else 1200, "height": 844 if touch else 900},
        has_touch=touch,
        is_mobile=touch,
    )
    page = open_page(browser, live_url(url), context=context)
    select_words(page, "#passage")
    if touch:
        selection_field(page).tap()
    write(page.locator(".lf-composer leaf-text"), "Please revisit this earlier plan.")
    with sending(page, "the long passage comment"):
        page.locator(".lf-composer button.lf-compose-submit").click()
    told(page)
    d = serve.page_dir
    root = next(e for e in events_model.read_events(d) if e["kind"] == "comment")
    replacement = source.replace(
        section,
        '<section id="'
        + ("current" if removed else "plan")
        + '"><h2>Current plan</h2><p'
        + ("" if removed else ' id="passage"')
        + ">The revised plan uses automatic review.</p></section>",
    )
    if removed:
        (d / "index.html").write_text(replacement)
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(d, root),
                "--detach",
                "--title",
                "Removed plan",
                "--text",
                "The earlier plan has been removed.",
            ],
        )
        assert result.exit_code == 0, result.output
    else:
        stamp_page(d, replacement, "Rewrote the plan")
    wait_for_revision(page, 2)
    choose_threads_in_panel(page)
    card = open_from_threads(page, root["id"])
    quote = card.locator(".lf-thread-quote")
    expect(quote).to_contain_text("FINAL IMPORTANT WORDS")
    if not removed:
        expect(card.locator(".lf-anchor-status")).to_have_text("Changed")
    # The panel's quote names no jump; Show on page takes the user to the passage.
    expect(quote).not_to_have_attribute("role", "button")
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure = card.locator(".lf-quote-label").get_by_role("button")
    expect(disclosure).to_be_visible()
    before = disclosure.bounding_box()
    if touch:
        # A finger reaches it across the 44px floor, by its face or, in the panel, by
        # the reach its face carries above and below.
        reach = disclosure.evaluate(
            """press => {
              const box = press.getBoundingClientRect();
              const x = box.left + box.width / 2, y = box.top + box.height / 2;
              return [-21.5, 21.5].every((by) => {
                const at = document.elementFromPoint(x, y + by);
                return at === press || press.contains(at);
              });
            }"""
        )
        assert reach, before
        disclosure.tap()
    else:
        disclosure.focus()
        page.keyboard.press("Enter")
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    after = disclosure.bounding_box()
    assert after["x"] == pytest.approx(before["x"], abs=1)
    assert after["y"] == pytest.approx(before["y"], abs=1)
    # A current-state repaint, independent of the quotation, preserves its local reading.
    append_agent_reply(d, root["id"], "I am checking the review requirement.")
    told(page)
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    stamp_page(
        d,
        replacement.replace(
            "</main>",
            '<p id="extra">The current plan has an unrelated note.</p></main>',
        ),
        "Added a separate note",
    )
    wait_for_revision(page, 3)
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    if touch:
        disclosure.tap()
    else:
        disclosure.click()
    expect(disclosure).to_have_attribute("aria-expanded", "false")
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")


def test_a_long_quote_of_replaced_data_has_a_local_reading(browser, serve):
    """A quote whose words a replacement took names no place on the page, and its card
    still reads the whole quote in place."""
    old = "The earlier deployment required a manual review before rollout. " * 12
    url = serve(
        leaf_page(
            "Earlier data quotation",
            '<h1 id="title">Deployment review</h1><lf-text-document id="source" source="document"></lf-text-document>',
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "document", old)
    page = open_page(browser, live_url(url))
    select_words(page, "#source .lf-text-document-run > *")
    write(page.locator(".lf-composer leaf-text"), "Does the manual review still apply?")
    with sending(page, "the earlier data comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    page_data_model.cmd_data_set(
        serve.page_dir, "document", "The deployment now uses automatic review."
    )
    told(page)
    root = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    card = open_from_threads(page, root["id"])
    quote = card.locator(".lf-thread-quote")
    expect(card.locator(".lf-thread-quote-head")).to_have_attribute(
        "data-lf-detached", ""
    )
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure = card.locator(".lf-quote-label").get_by_role("button")
    expect(disclosure).to_be_visible()
    compact = card.bounding_box()["height"]
    compact_quote = quote.bounding_box()["height"]
    disclosure.click()
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    rendered(page)
    assert quote.bounding_box()["height"] > compact_quote
    assert card.bounding_box()["height"] == pytest.approx(compact, abs=0.5)
    assert card.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure.click()
    rendered(page)
    assert card.bounding_box()["height"] == pytest.approx(compact, abs=0.5)
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")


def test_a_thread_s_head_names_the_headings_over_its_words(browser, serve):
    """A thread's head names the headings the reader passes to reach its words,
    outermost first: a flow of h2s stands under the h1 before them, not under the h2
    before it. Quoted words with no place of their own carry them as their label, and
    words no heading stands over carry the page's title, so the label is there before
    a revision gives the words a status. A thread on a place carries its place as its
    label and the headings as its title, and a heading's own names only those over it."""
    url = serve(
        leaf_page(
            "Release notes",
            '<p id="lede">Read this first.</p>'
            '<h1 id="title">Release plan</h1><h2 id="first">Staging</h2>'
            '<p id="staging">Staging takes a day.</p>'
            '<h2 id="rollout">Rollout</h2><h3 id="canary">Canary hosts</h3>'
            '<p id="hosts">Two hosts take the first build.</p>',
        )
    )
    on_words = panel_comment(
        serve.page_dir, "Which hosts?", {"section": "hosts", "quote": "Two hosts"}
    )
    on_lede = panel_comment(
        serve.page_dir, "Is this needed?", {"section": "lede", "quote": "Read this"}
    )
    on_heading = panel_comment(serve.page_dir, "Rename this?", {"section": "rollout"})
    page = open_page(browser, url)
    # The head is the panel view's: a card beside words no revision changed draws none.
    choose_threads_in_panel(page)
    for thread, label in (
        (on_words, "Release plan › Rollout › Canary hosts"),
        (on_lede, "Release notes"),
    ):
        head = open_from_threads(page, thread).locator(".lf-thread-quote-head")
        expect(head.locator(".lf-quote-label")).to_have_text(label)
        expect(head).not_to_have_attribute("title", re.compile(".*"))
    head = open_from_threads(page, on_heading).locator(".lf-thread-quote-head")
    expect(head.locator(".lf-quote-label")).to_have_text("§ heading · Rollout")
    expect(head).to_have_attribute("title", "Release plan")


@pytest.mark.parametrize("quoted", [True, False], ids=["short-quote", "whole-section"])
def test_a_retained_reference_with_nothing_hidden_offers_no_disclosure(
    browser, serve, quoted
):
    source = leaf_page(
        "Short retained reference",
        '<h1 id="title">Plan</h1><p id="plan">Manual review first.</p>',
    )
    url = serve(source)
    anchor = {
        "section": "plan",
        **({"quote": "Manual review first."} if quoted else {}),
    }
    root = panel_comment(serve.page_dir, "Does this still apply?", anchor)
    page = open_page(browser, live_url(url))
    stamp_page(
        serve.page_dir,
        source.replace(
            '<p id="plan">Manual review first.</p>',
            '<p id="new-plan">Automatic review.</p>',
        ),
        "Replaced the plan",
    )
    wait_for_revision(page, 2)
    card = open_from_threads(page, root)
    expect(card.locator(".lf-thread-quote-head")).to_be_visible()
    expect(card.locator(".lf-quote-label").get_by_role("button")).to_have_count(0)


# How an opened quote shows its words: its sizes, whether they all fit, and whether
# it scrolls to the rest.
QUOTE_ROOM = """el => ({
  height: el.clientHeight,
  words: el.scrollHeight,
  whole: el.scrollHeight <= el.clientHeight + 1,
  scrolls: ['auto', 'scroll'].includes(getComputedStyle(el).overflowY),
})"""


def test_a_changed_datum_keeps_its_old_words_open_when_its_label_changes(
    browser, serve
):
    """Subject identity survives a rewrite; neither its label nor location is the quote."""
    old = "The original requirement keeps a human review before release. " * 12
    module = """
import { html } from '/vendor/lit.js';
import { LeafElement } from '/runtime/lib/leaf-element.js';
customElements.define('lf-quote-subject', class extends LeafElement {
  static properties = {label: {attribute: false}, words: {attribute: false}};
  setup() {
    window.quoteSubject = this;
    this.show('Old plan', this.dataset.words);
  }
  show(label, words) {
    this.label = label;
    this.words = words;
  }
  render() {
    return html`<p data-lf-datum="plan" data-lf-identity="plan"
      data-lf-datum-label=${this.label}>${this.words}</p>`;
  }
  updated(changed) {
    super.updated(changed);
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: this.words}}));
  }
});
"""
    url = serve(
        leaf_page(
            "Retained subject words",
            '<h1 id="title">Release review</h1>'
            f'<lf-quote-subject id="subject" data-words="{old}"></lf-quote-subject>',
        ),
        layer_registry={
            "lf-quote-subject": {
                "description": "A named subject whose wording changes.",
                "attributes": {
                    "properties": {
                        "data-words": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["id"],
                },
                "content": "empty",
                "inputs": {
                    "words": {
                        "contract": "text-document",
                        "source": "source",
                        "property": "value",
                    }
                },
                "example": '<lf-quote-subject id="example"></lf-quote-subject>',
            }
        },
        layer_widgets={"lf-quote-subject.js": module},
    )
    page = open_page(browser, live_url(url))
    select_words(page, "#subject p")
    write(
        page.locator(".lf-composer leaf-text"), "Does the original review still apply?"
    )
    with sending(page, "the subject quotation"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    comment = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    page.evaluate(
        "window.quoteSubject.show('Old plan', 'The revised requirement uses automatic review.')"
    )
    reading = page.evaluate(
        """anchor => window.__lfCheckApi()
          .then(({resolveAnchor}) => {const {kind, exact, status} = resolveAnchor(anchor);
            return {kind, exact, status};})""",
        comment["anchor"],
    )
    assert reading == {"kind": "element", "exact": False, "status": "fallback"}
    card = open_from_threads(page, comment["id"])
    quote = card.locator(".lf-thread-quote")
    expect(card.locator(".lf-anchor-status")).to_have_text("Changed")
    disclosure = card.locator(".lf-quote-label").get_by_role("button")
    disclosure.click()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    # The relabel alone repaints the quote, by the time the page has drawn it: nothing
    # the press began is still painting, and no later paint is waited for.
    rendered(page)
    opened = quote.evaluate(QUOTE_ROOM)
    page.evaluate(
        "window.quoteSubject.show('Current plan', 'The revised requirement uses automatic review.')"
    )
    rendered(page)
    assert "Current plan" in card.locator(".lf-quote-label").inner_text()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    # The old words stay open as they were: whole where the card has room for them,
    # else scrolling in the quote's own share of a slim card.
    assert quote.evaluate(QUOTE_ROOM) == opened
    assert opened["whole"] or opened["scrolls"], opened
