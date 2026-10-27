"""What a thread stands on and how its card shows it: passage links, marks on widgets in
an agent's reply, and quotes of words the page has since rewritten."""

import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, response_reference
from playwright.sync_api import expect
from render_cases_interaction import LIST_ORDER, PANEL_PAGE, live_url, panel_comment
from render_harness import (
    EXAMPLE_PACKAGES,
    PANEL_THREAD,
    any_owner_entry,
    leaf_page,
    open_page,
    open_threads,
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
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def open_from_threads(page, root):
    """Open the thread `root` from its row in the panel's Threads, as a reader finds it,
    and return what shows it: the panel's view, or its passage's margin card."""
    thread_row(page, root).click()
    view = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    margin = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
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
                    "anchor": {"section": "inside"},
                }
            ],
        ),
    )
    panel = page.locator("#first")
    expect(panel).to_have_attribute("tabindex", "0")
    passage = page.locator("#inside")
    passage.hover()
    expect(passage).to_have_css("cursor", "pointer")
    passage.click()
    expect(
        page.locator('.lf-margin-preview .lf-page-thread[data-thread="inside-thread"]')
    ).to_be_visible()


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
    the ones below it."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    patch = panel_comment(
        d, "Twelve is arbitrary.", {"quote": "the ceiling doubles per approval"}
    )
    both = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page = open_page(browser, url)
    open_threads(page)
    # The passage really is inside the widget's shadow tree, so the reading under test is
    # the cross-tree one rather than an ordinary document comparison.
    assert page.evaluate(
        """() => {
             const root = document.getElementById('how-patch').shadowRoot;
             return Boolean(root) && [...(CSS.highlights.get('lf-mark') ?? [])]
               .some((r) => root.contains(r.startContainer));
           }"""
    ), "the fixture's passage is not marked inside a shadow tree"
    assert page.evaluate(LIST_ORDER) == [
        lede,
        patch,
        both,
    ], "the thread on the widget's words does not stand where the widget does"


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


def test_a_mark_in_the_layer_promises_no_press_the_layer_will_not_take(browser, serve):
    """An outline in the chrome says which element, and stops there.

    An element anchor wears its outline wherever its element stands, the layer's own
    parts included — that is what lets a design comment about the banner point at the
    banner. What the outline may not do there is offer the hand: `markAt` refuses a
    press inside the chrome on purpose, because what the chrome holds keeps its own
    presses. The Threads button opens the panel and an option takes a pick; neither
    of them opens a thread. So the pointer stood over a marked question an agent had
    asked, promising a click nothing took.

    The page's own mark is the control, and it keeps the hand it has always had."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-ask id="tv-decision-region"><h3>Which store should I write up?</h3>'
        '<lf-options id="tv-decision" choose>'
        '<lf-option id="tv-redis">Redis</lf-option>'
        "</lf-options></lf-ask>",
        "tv-decision",
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-on-page",
            "author": "user",
            "revision": 1,
            "text": "About the page.",
            "anchor": {"section": "tv-p3"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    open_panel_thread(page, "tv-decisioned")
    rendered(page)

    marks = page.evaluate(
        """() => [...document.querySelectorAll('.lf-mark-el')].map((el) => ({
             id: el.id, chrome: Boolean(el.closest('.lf-floating-panel')),
             cursor: getComputedStyle(el).cursor,
           }))"""
    )
    inside = [m for m in marks if m["chrome"]]
    outside = [m for m in marks if not m["chrome"]]
    assert inside and outside, (
        f"this needs a mark in each document to compare; got {marks}"
    )
    assert all(m["cursor"] == "pointer" for m in outside), (
        f"the page's own mark lost its hand, so the reading below is about nothing: "
        f"{outside}"
    )
    assert all(m["cursor"] != "pointer" for m in inside), (
        f"a mark in the layer offers the hand and no press is taken there: {inside}"
    )
    # And the other half of the sentence, since a cursor is only a promise about a
    # press: the press itself, on the marked widget's own words, reaching no thread.
    page.locator(".lf-fp-view #tv-decision").click(position={"x": 4, "y": 4})
    rendered(page)
    expect(page.locator(f'{PANEL_THREAD}[data-thread="tv-decisioned"]')).to_be_visible()
    assert not page.locator(f'{PANEL_THREAD}[data-thread="tv-on-it"]').count(), (
        "a press on a mark in the layer reached its thread after all"
    )


def test_a_control_in_a_reply_holds_the_page_s_control_shape(browser, serve):
    """A change sent in a reply keeps the canonical circular control.

    A reply is upgraded inside a closed comment panel, where its box is zero, and its
    controls used to be measured there and collapse. The control's circle is fixed,
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
    with service_model.PageTransaction(serve.page_dir) as transaction:
        for event in (
            {
                "kind": "reply",
                "author": "agent",
                "parent": "tv-decisioned",
                "revision": 1,
                "text": "Depends what you want to keep:",
                "markup": '<lf-options id="tv-decision">'
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
      const { layoutChanged } = await window.__lfWidgetApi();
      const { whenDocumentPresented } = await window.__lfCheckApi();
      const old = document.querySelector('.lf-fp-view #tv-redis');
      const replacement = old.cloneNode(true);
      replacement.classList.remove('lf-mark-el');
      old.replaceWith(replacement);
      await layoutChanged(document.querySelector('.lf-fp-view #tv-decision'));
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
    box, which is what a mark hangs on and what a decision's ring hangs on. It kept the
    runtime's own apparatus out of that fallback by asking whether each child was
    under the runtime's chrome, and a widget an agent sent in a reply is: the panel
    over it answers for every child, so the fallback filtered all of them away and the
    widget showed as nothing at all. Bounded at the widget, the panel above it is no
    longer its own apparatus and the parts come back.

    `display: contents` on a widget is a page's line to write — the shipped vocabulary
    has none today, and `shownParts` exists because any layer can. A widget in a reply
    stands in the chrome, so the page's rule names it there, which outweighs the chrome's
    guard against light page rules (styles/chrome-guard.css)."""
    page_source = REPLY_TRAVEL_PAGE.replace(
        "</head>",
        "<style>.lf-chrome lf-options { display: contents }</style>\n</head>",
    )
    url = serve(page_source, packages=EXAMPLE_PACKAGES)
    # The page's unlayered style puts a reporting group's wrapper in `contents`; the
    # subject is the boxless wrapper fallback, not package-theme precedence.
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-decision">'
        '<lf-option id="tv-redis" chosen>Redis</lf-option>'
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
    the text, so a thread anchored on one was quoted as "redblue". The module that
    names its own kind (x-word) names its own words the same way."""
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
                "--text",
                "The earlier plan has been removed.",
            ],
        )
        assert result.exit_code == 0, result.output
    else:
        stamp_page(d, replacement, "Rewrote the plan")
    wait_for_revision(page, 2)
    card = open_from_threads(page, root["id"])
    quote = card.locator(".lf-quote")
    expect(quote).to_contain_text("FINAL IMPORTANT WORDS")
    if not removed:
        expect(quote.locator(".lf-anchor-status")).to_have_text("Changed")
    # A margin card's quote returns to the passage where it still stands; the panel's
    # names no jump.
    in_panel = card.evaluate("node => node.matches('.lf-fp-view')")
    if removed or in_panel:
        expect(quote).not_to_have_attribute("role", "button")
    else:
        expect(quote).to_have_attribute("role", "button")
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure = card.get_by_role("button", name="Full quote", exact=True)
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
    """A surviving widget is a destination, but cannot show the old data's words."""
    old = "The earlier deployment required a manual review before rollout. " * 12
    url = serve(
        leaf_page(
            "Earlier data quotation",
            '<h1 id="title">Deployment review</h1><lf-text-document id="source" source="document"></lf-text-document>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "document", old)
    page = open_page(browser, live_url(url))
    # The code box's first child is the gutter; triple-click the rendered words.
    select_words(page, "#source [data-content] [data-line] span")
    write(page.locator(".lf-composer leaf-text"), "Does the manual review still apply?")
    with sending(page, "the earlier data comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    data_model.cmd_data_set(
        serve.page_dir, "document", "The deployment now uses automatic review."
    )
    told(page)
    root = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    card = open_from_threads(page, root["id"])
    quote = card.locator(".lf-quote")
    expect(quote.locator(".lf-anchor-status")).to_have_text("Earlier data")
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure = card.get_by_role("button", name="Full quote", exact=True)
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
    expect(card.locator(".lf-quote")).to_be_visible()
    expect(
        card.get_by_role("button", name="Full quote", exact=True)
    ).not_to_be_visible()


def test_a_changed_datum_keeps_its_old_words_open_when_its_label_changes(
    browser, serve
):
    """Subject identity survives a rewrite; neither its label nor location is the quote."""
    old = "The original requirement keeps a human review before release. " * 12
    module = """
import {LeafElement, html} from '/runtime/widget-api.js';
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
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "data-words": {"type": "string"},
                    "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                },
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "empty",
                "x-data": {
                    "words": {
                        "contract": "text-document",
                        "source": "source",
                        "property": "value",
                    }
                },
                "x-upgrade": True,
                "x-example": '<lf-quote-subject id="example"></lf-quote-subject>',
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
    quote = card.locator(".lf-quote")
    expect(quote).not_to_have_attribute("title", "Jump to this passage")
    expect(quote.locator(".lf-anchor-status")).to_have_text("Changed")
    disclosure = card.get_by_role("button", name="Full quote", exact=True)
    disclosure.click()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    # The relabel alone repaints the quote, by the time the page has drawn it: nothing
    # the press began is still painting, and no later paint is waited for.
    rendered(page)
    page.evaluate(
        "window.quoteSubject.show('Current plan', 'The revised requirement uses automatic review.')"
    )
    rendered(page)
    assert "Current plan" in quote.inner_text()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
