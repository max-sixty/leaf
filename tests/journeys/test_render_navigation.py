"""Comment marks, Go-to addresses, keyboard navigation, the feature gallery's
journeys through its tabs and the core surfaces, and the keys each element names as
the user moves through the examples."""

import json
import random
import re

import pytest
from browser.margin.test_entries import _refreshes_restate_no_margin_name
from browser.navigation import (
    READING_REGIONS_PAGE,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    answered_comment,
    live_url,
    serve_obligations,
)
from render_cases_layout import page_at_rest, token_colour
from render_cases_navigation import (
    ADDRESSED_PAGE,
    CHIPS,
    address_code,
    address_codes,
    go_to_address,
)
from render_harness import (
    FEATURE_GALLERY,
    PANEL,
    PREVIEW,
    RELEASE_FOCUS,
    all_pages_offered,
    command_reference_rows,
    expect_obligations_answered,
    expect_open_threads,
    expect_panel_says,
    leaf_page,
    margins_laid_out,
    navigate,
    open_page,
    open_threads,
    opened_tab,
    pane_scroll_behavior,
    panel_control,
    panel_says,
    panel_settled,
    panel_view,
    preview_parts,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
)

from journeys import expect_showing
from leaf.base import server as server_model
from leaf.log import event_log as events_model
from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, start_near_work, wait_until_ready
from leaf_dev.browser import PANEL_THREAD, show_resolved, text_field
from leaf_dev.example_data import named_source, published_sources

pytestmark = pytest.mark.shifts_unsurveyed


def go_to_passage(page, page_dir, words):
    """Open the thread quoting `words` in the panel and go to the passage with its
    view's Show on page."""
    thread = next(
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment" and event["anchor"].get("quote") == words
    )
    open_panel_thread(page, thread)
    page.locator(".lf-fp-head").get_by_role("button", name="Show on page").click()


# An obligation's digits beside a page-scoped command with a context key of its own,
# registered the way an authored module does.
QUICK_KEYS_PAGE = leaf_page(
    "quick keys",
    """
<h1 id="title">Field day</h1>
<lf-group id="map-ask" label="Which map should the sample team carry?">
  <h3 id="map-ask-h">Which map should the sample team carry?</h3>
  <lf-options id="map">
    <lf-option id="map-street">Street map</lf-option>
    <lf-option id="map-trail">Trail map</lf-option>
  </lf-options>
</lf-group>
<div id="local-shortcuts" tabindex="0">
  <button id="shortcut-focus-note" type="button">Write sample note</button>
  <label>Sample note <input id="shortcut-note" type="text" /></label>
</div>
""",
    head="""<script type="module">
const note = document.querySelector("#shortcut-note");
document.querySelector("#local-shortcuts").lfCommands = { title: "In the note sample", rows: [{
  id: "note.focus",
  contextKeys: ["1"],
  control: document.querySelector("#shortcut-focus-note"),
  bindingBadge: null,
  title: "Write note",
  description: "Focus the sample note",
  run: () => note.focus(),
}] };
document.querySelector("#local-shortcuts").dispatchEvent(new CustomEvent("lf-commands", { bubbles: true, composed: true }));
</script>""",
)


def test_a_let_go_keeps_the_user_in_the_pane_they_read(browser, serve):
    """A let-go lands on what the user is reading in the page region they last acted
    in. It guards two failures: opening Threads over a pane replacing that region with
    the panel's list, so closing it lands on the workspace header; and a pane showing
    no words where it stands (a figure, a spacer) having no block to land on, so the
    user is dropped on the body and the pane forgotten. Either way `d` and `u` stop
    moving the pane.

    A pane that flows inside a scrolling workspace body keeps answering after it scrolls
    out of the window, which a test of the pane's own visibility must not mistake for a
    closed surface."""
    tops = """() => ['left-reading', 'right-reading'].map((id) =>
      document.querySelector(`#${id} > :not(header, footer)`).scrollTop)"""
    reading = """async () => (await window.__lfCheckApi()).userReadingRegion()?.host.id ?? null"""
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    resized(page, 1440, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")

    page.locator("#right-head").focus()
    assert page.evaluate(reading) == "right-reading"
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(panel_view("threads"))).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    # Closing the focused view leaves body active. It is no selected passage;
    # the landing must read the remembered pane rather than scan the whole page.
    assert page.evaluate(reading) == "right-reading"
    page.keyboard.press("d")
    page.wait_for_function(f"() => ({tops})()[1] > 0")

    page.locator("#left-reading > :not(header, footer)").evaluate(
        "body => body.scrollTop = 400"
    )
    page.locator("#left-head").focus()
    page.keyboard.press("Escape")
    assert page.evaluate(reading) == "left-reading"
    page.keyboard.press("u")
    page.wait_for_function(f"() => ({tops})()[0] < 400")

    flowing = READING_REGIONS_PAGE.replace(
        '<lf-pane id="left-reading"', '<section><lf-pane id="left-reading"'
    ).replace("    </lf-pane>\n  </div>", "    </lf-pane></section>\n  </div>")
    assert flowing.count("</section>") == 1
    page = open_page(browser, serve(flowing))
    resized(page, 1440, 900)
    split = page.locator("#reading-split")
    page.locator("#left-start").click()
    for _ in range(12):
        page.keyboard.press("d")
        page.wait_for_timeout(200)
    assert (
        split.evaluate("box => box.scrollHeight - box.clientHeight - box.scrollTop") < 2
    )
    # The pane it remembers has scrolled out of view, so a landing reads the body
    # carrying it, which shows the other pane, rather than going back for the first.
    bottom = split.evaluate("box => box.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("p")
    page.keyboard.press("Tab")
    expect(page.locator("#right-subject")).to_be_focused()
    assert split.evaluate("box => box.scrollTop") == bottom


def test_review_queue_decisions_replay_and_reach_the_next_revision_from_the_keyboard(
    browser, serve
):
    example = named_source("review-queue")

    seeded = serve(example)
    first = seeded.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_obligations_answered(page, "2/2")
    expect(page.locator("#review-cache-auto")).to_have_attribute("selected", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("selected", "")
    page.close()

    newest = serve(example, seed_log=False)
    first = newest.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_obligations_answered(page, "0/2")
    expect(page.locator("#review-cache-auto")).not_to_have_attribute("selected", "")
    expect(page.locator("#review-billing-legacy")).not_to_have_attribute("selected", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "A failed copy leaves the old keys authoritative"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Open difference"
    )
    footer = page.locator("#review-detail > footer")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")
    expect(footer).to_contain_text(
        "submitted answers are incorporated in the next revision"
    )

    page.keyboard.press("m")
    expect(page.locator("#review-cache-decision")).to_be_focused()
    with sending(page, "the cache rollback decision"):
        page.keyboard.press("1")
    expect(page.locator("#review-cache-auto")).to_have_attribute("selected", "")

    page.keyboard.press("m")
    expect(page.locator("#review-billing-decision")).to_be_focused()
    with sending(page, "the billing reconciliation decision"):
        page.keyboard.press("1")
    expect_obligations_answered(page, "2/2")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")

    page.goto(live_url(newest))
    rendered(page)
    expect_showing(page, 2)
    expect(page.locator("#review-cache-auto")).to_have_attribute("selected", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("selected", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "returns readers to the old keys automatically"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Legacy difference stays on its reporting path"
    )
    expect(page.locator("#review-detail > footer")).to_contain_text(
        "This revision incorporates both answers"
    )
    # The revision settles both questions; the obligation inventory retains answers
    # after an authored revision settles their sources (`obligations.py`).
    expect_obligations_answered(page, "2/2")

    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in actions] == [
        ["review-cache-auto"],
        ["review-billing-legacy"],
    ]


def test_inner_state_is_left_before_the_surface_around_it(browser, serve):
    """The current page location unwinds before the panel view around it.

    An Ask stood on while On Me stands lets go first, then On Me. A thread's Ask
    reached by `m` with Threads open stands in the thread's margin card, since the
    panel declines a thread about a passage. Escape closes that card beside its
    target in one press, and only the next press puts Threads away."""
    # A page obligation stood on while On Me, which the keyboard opened, stands over the page.
    page = open_page(browser, serve_obligations(serve))
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    item = page.locator("#live-question-decision")
    item.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(item).to_be_focused()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "queue")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # `m` from a heading into a thread's obligation, with Threads already open: each Escape
    # leaves one layer, the innermost first, without returning to the heading.
    page = open_page(browser, serve(named_source("ship-review")))
    open_threads(page)
    heading = page.locator("main h2").first
    heading.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(heading).to_be_focused()
    page.keyboard.press("m")
    card = page.locator(".lf-margin-preview")
    expect(card.locator("lf-group[data-lf-obligation]")).to_be_focused()
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "threads")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")


def test_the_g_chord_reaches_the_all_leaves_panel(browser, serve, live_leaf):
    """All pages is a destination of the panel's and follows the same focus contract."""
    live_leaf("second", "A second leaf")
    page = open_page(browser, serve(ADDRESSED_PAGE))
    all_pages_offered(page)

    page.keyboard.press("g")
    # A live page arriving while the sequence stands keeps its destination operable.
    live_leaf("third", "A third leaf")
    round_trip(page)
    page.keyboard.press("Shift+l")

    panel_settled(page, view="leaves")
    leaves = page.locator(panel_view("leaves"))
    expect(leaves.locator(".lf-fp-page[href]")).to_have_count(2)
    expect(leaves.locator(".lf-fp-page[href]").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)


def test_a_box_that_starts_scrolling_after_it_arrives_takes_a_stop(browser, serve):
    """A declared scroll surface (`class="lf-scroll"`) that starts scrolling after the page
    loads is reachable, shows its edge mark, and starts the sticky-header slot again, as
    it does when the page loads with it scrolling: whether a shorter window, a narrower container, or a page script made
    it scroll, by a class it adds as it adapts to the box's size or by a box it inserts,
    and announced it with an `lf-layout` event. A box the window grows out of scrolling gives
    all three back. The window's case asks its height, which no box's size follows. A
    table first drawn when its disclosure opens is read in the size delivery that draws
    it, and a script announcing from a size delivery is heard, both without a
    ResizeObserver loop. A column's sidebar the page loads seated in the margin, where
    the Layout makes it scroll, takes its stop as one the window widened into the
    margin does. A size container a page animates for as long as it plays holds back
    neither the others nor the page's settling, though a script announces it."""
    wide = '<div class="wide">A block held to nine hundred pixels wide.</div>'
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Late scrollers",
                '<div id="meter"></div>'
                f'<div id="by-window" class="lf-scroll">{wide}</div>'
                '<div id="holder">'
                f'<div id="by-container" class="lf-scroll">{wide}</div></div>'
                f'<div id="by-script" class="lf-scroll">{wide}</div>'
                '<details id="more"><summary>More</summary><table id="drawn"><tbody>'
                "<tr><td>Cell</td></tr></tbody></table></details>",
                head="<style>.wide { width: 900px; }"
                "@media (height < 860px) { #by-window { overflow-x: auto; } }"
                "#holder { container-type: inline-size; width: 800px; }"
                "@container (width < 600px) { #by-container { overflow-x: auto; } }"
                "#by-script.scrolls, #by-insert { overflow-x: auto; }"
                "@keyframes pulse { from { width: 120px; } to { width: 160px; } }"
                "#meter { container-type: inline-size; block-size: 8px;"
                " animation: pulse 1s linear infinite; }</style>",
            )
        ),
    )
    resized(page, 1200, 900)
    names = ("window", "container", "script")
    boxes = {name: page.locator(f"#by-{name}") for name in names}
    for box in boxes.values():
        expect(box).not_to_have_attribute("data-lf-scrolls", "")

    resized(page, 1200, 800)
    page.evaluate(
        """async () => {
        document.getElementById('holder').style.width = '400px';
        const box = document.getElementById('by-script');
        new ResizeObserver((entries, observer) => {
            observer.disconnect();
            box.classList.add('scrolls');
            box.dispatchEvent(new CustomEvent('lf-layout', { bubbles: true, composed: true }));
        }).observe(box);
        const inserted = document.createElement('div');
        inserted.id = 'by-insert';
        inserted.className = 'lf-scroll';
        inserted.innerHTML = '<div class="wide">An inserted block.</div>';
        document.querySelector('main').append(inserted);
        inserted.dispatchEvent(new CustomEvent('lf-layout', { bubbles: true, composed: true }));
        document.getElementById('meter').dispatchEvent(new CustomEvent('lf-layout', { bubbles: true, composed: true }));
    }"""
    )
    boxes["insert"] = page.locator("#by-insert")
    for box in boxes.values():
        expect(box).to_have_attribute("data-lf-more-after", "")
        expect(box).to_have_attribute("tabindex", "0")
        expect(box).to_have_attribute("data-lf-scrolls", "")

    resized(page, 1200, 900)
    window_box = boxes["window"]
    expect(window_box).not_to_have_attribute("data-lf-scrolls", "")
    expect(window_box).not_to_have_attribute("data-lf-more-after", "")
    expect(window_box).not_to_have_attribute("tabindex", "0")

    rendered(page)

    page.evaluate(
        "() => { document.getElementById('meter').style.animation = 'none'; }"
    )
    rendered(page)
    page.locator("#more > summary").click()
    # The theme scrolls a table only sideways, which the slot reads as `across`.
    expect(page.locator("#drawn")).to_have_attribute("data-lf-scrolls", "across")

    entries = "".join(f"<li>Sidebar entry {n}</li>" for n in range(40))
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Seated sidebar",
                f'<aside><div class="layout-track" id="side"><ul>{entries}</ul></div></aside>'
                '<div class="layout-column"><h1>Seated sidebar</h1>'
                + "<p>Filler.</p>" * 30
                + "</div>",
                layout="sidebar",
            )
        ),
        context=browser.new_context(viewport={"width": 1600, "height": 900}),
    )
    expect(page.locator("#side")).to_have_css("position", "sticky")
    expect(page.locator("#side")).to_have_attribute("tabindex", "0")


def test_c_leaves_an_item_its_own_scroller_has_taken_away(browser, serve):
    """What the press asks is whether the item is in front of the user, and only the
    page shows that. An item's own box is the box it would have — unclipped — so a card
    carried out of a board's sideways scroller still reports one inside the window, and a
    gate reading that called it visible opened the box on something entirely off screen.
    A key pressed there lets go of the card first, so `c` opens the page's own field and
    leaves the board where the user scrolled it.

    The control is the same board with the scroller left alone, where the card is really
    in front of the user and `c` comments on it where it stands. A test with only the
    scrolled case would pass just as well on a press that never reached the card."""
    url = serve(
        leaf_page(
            "carried",
            """
<h1 id="t">Carried</h1>
<lf-board id="b">
"""
            + "\n".join(
                f'<lf-column id="col{i}" label="Column {i}">'
                f'<lf-card id="card{i}">Card {i} with a '
                f'<a href="https://example.invalid/{i}">link {i}</a> inside it.</lf-card>'
                "</lf-column>"
                for i in range(8)
            )
            + """
</lf-board>
""",
        )
    )
    seen = """() => {
      const r = document.querySelector('#card0').getBoundingClientRect();
      const b = document.querySelector('#b').getBoundingClientRect();
      return {
        left: Math.round(r.left),
        onScreen: r.right > 0 && r.left < innerWidth,
        visible: Math.max(0, Math.min(r.right, b.right, innerWidth)
          - Math.max(r.left, b.left, 0)),
        width: r.width,
      };
    }"""

    # The control: nothing scrolled, so the card is in front of the user and stays put.
    page = open_page(browser, url)
    page.locator("#card0 a").focus()
    was = page.evaluate(seen)
    assert was["onScreen"], "the control needs the card visible to begin with"
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["left"] == was["left"], (
        "the page moved under a user who could already see the card"
    )
    page.close()

    # The card itself with only the board's next-item cue left in view. The sliver is
    # still where the user is and supplies an attachment, so opening Comment preserves
    # the board.
    page = open_page(browser, url)
    page.locator("#card0").evaluate("card => { card.tabIndex = -1; card.focus(); }")
    page.evaluate(
        """() => {
          const card = document.querySelector('#card0');
          document.querySelector('#b').scrollLeft = card.getBoundingClientRect().width - 7;
        }"""
    )
    was = page.evaluate(seen)
    assert 0 < was["visible"] < was["width"] / 4, was
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    now = page.evaluate(seen)
    assert now == was
    page.close()

    # Carried out of its own scroller after the user was located on it — focus first, because
    # focusing a card is itself a scroll and would undo the carrying it is meant to survive.
    page = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        "() => { const b = document.querySelector('#b'); b.scrollLeft = b.scrollWidth; }"
    )
    assert not page.evaluate(seen)["onScreen"], (
        "the board did not carry the card off screen, so this proves nothing"
    )
    page.keyboard.press("c")
    expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert not page.evaluate(seen)["onScreen"], (
        "the press took the board from where the user scrolled it"
    )


def test_quick_shortcuts_can_be_disabled_without_withdrawing_commands(browser, serve):
    """One persistent policy covers page keys, contextual digits and their hints."""
    page = open_page(browser, serve(QUICK_KEYS_PAGE))
    reference = page.locator(".lf-command-reference")
    setting = page.get_by_role("checkbox", name="Quick keyboard shortcuts", exact=True)
    note = page.locator("#shortcut-note")
    button = page.locator("#shortcut-focus-note")
    sample = page.locator("#local-shortcuts")

    def settings():
        panel_control(page, "keyboard").click()
        expect(reference).to_be_visible()

    sample.focus()
    expect(button).to_have_attribute("aria-keyshortcuts", "1")
    page.keyboard.press("1")
    expect(note).to_be_focused()
    page.keyboard.type("c ? 1 T")
    expect(note).to_have_value("c ? 1 T")
    settings()
    expect(setting).to_be_checked()
    expect(setting).to_have_accessible_description(
        "Use letters, numbers and symbols for Leaf actions."
    )
    # The preference itself is reachable by Tab and native Space.
    page.get_by_role("combobox", name="Search commands").press("Shift+Tab")
    expect(setting).to_be_focused()
    setting.press("Space")
    expect(setting).not_to_be_checked()
    comment = reference.locator('[role=option][data-lf-command="comment.create"]')
    expect(comment.locator("kbd")).to_have_count(0)
    # Disabling the key makes the command actionable even from the text field where
    # that key was previously reserved for typing.
    page.get_by_role("combobox", name="Search commands").fill("Comment on the page")
    expect(comment).to_have_attribute("data-lf-available", "true")
    page.get_by_role("button", name="Close the command reference").click()
    page.locator("body").focus()
    settings()
    page.get_by_role("combobox", name="Search commands").fill("Comment on the page")
    comment.click()
    field = text_field(page, name="Comment on the page", exact=True)
    expect(field).to_be_focused()
    page.keyboard.type("Sent with quick shortcuts off")
    page.keyboard.press("ControlOrMeta+Enter")
    # Send opens the new thread's view, the field becoming its reply.
    expect(page.locator(PANEL_THREAD)).to_be_visible()
    told(page)
    assert any(
        event.get("text") == "Sent with quick shortcuts off"
        for event in events_model.read_events(serve.page_dir)
    )
    rendered(page)

    sample.focus()
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    for key in ("1", "c", "?", "Shift+t", "g", "Shift+t"):
        page.keyboard.press(key)
    rendered(page)
    expect(sample).to_be_focused()
    expect(reference).to_be_hidden()
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    expect(button).not_to_have_attribute("title", re.compile(r"\(1\)"))
    settings()
    page.get_by_role("combobox", name="Search commands").fill("Select mode")
    reference.locator('[role=option][data-lf-command="target.picker.open"]').click()
    rendered(page)
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    expect(page.locator(".lf-live")).not_to_contain_text("type one of")
    page.keyboard.press("a")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("Enter choose target")
    expect(page.locator(".lf-live")).not_to_contain_text("Hint ")
    native_target = page.locator('[data-lf-hint-native="Enter"]')
    expect(native_target).to_be_visible()
    expect(native_target).not_to_have_attribute("data-lf-hint-code")
    expect(native_target.locator("kbd")).to_have_text("⏎")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(native_target).to_have_count(0)
    page.keyboard.press("Escape")
    rendered(page)
    street = page.locator("#map-street")
    trail = page.locator("#map-trail")
    street.locator(".lf-pick").focus()
    expect(page.locator("#map")).not_to_have_attribute(
        "aria-keyshortcuts", re.compile(r"(?:^| )1(?: |$)")
    )
    page.keyboard.press("1")
    rendered(page)
    expect(street).not_to_have_attribute("selected", "")
    street.locator(".lf-pick").focus()
    page.keyboard.press("ArrowDown")
    expect(trail.locator(".lf-pick")).to_be_focused()
    page.keyboard.press("Space")
    expect(trail).to_have_attribute("selected", "")
    button.focus()
    button.press("Enter")
    expect(note).to_be_focused()
    note.press("End")
    page.keyboard.type(" native")
    expect(note).to_have_value("c ? 1 T native")

    page.reload()
    wait_until_ready(page)
    sample.focus()
    page.keyboard.press("1")
    rendered(page)
    expect(sample).to_be_focused()
    settings()
    expect(setting).not_to_be_checked()
    setting.check()
    page.keyboard.press("Escape")
    street.locator(".lf-pick").focus()
    expect(page.locator("#map")).to_have_attribute(
        "aria-keyshortcuts", re.compile(r"(?:^| )1(?: |$)")
    )
    page.keyboard.press("1")
    expect(street).to_have_attribute("selected", "")
    sample.focus()
    expect(button).to_have_attribute("aria-keyshortcuts", "1")
    page.keyboard.press("1")
    expect(note).to_be_focused()

    page.locator("body").focus()
    settings()
    page.get_by_role("combobox", name="Search commands").fill("Select mode")
    reference.locator('[role=option][data-lf-command="target.picker.open"]').click()
    rendered(page)
    expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
    page.keyboard.press("Escape")


# The gallery sections a preview may name, and the page tab each opens.
GALLERY_DESTINATIONS = {
    "bg-core-surfaces": "Decisions",
    "bg-thread-states": "Threads",
    "bg-panel-views": "Threads",
    "bg-quoted-and-visual": "Page & layout",
    "bg-external-data": "Data & work",
    "bg-interactions": "Interactions",
}


@pytest.mark.watch_shifts
def test_the_feature_gallery_exercises_its_core_journeys(browser, serve, live_leaf):
    """The gallery is a journey through the core, not merely its samples beside it.

    A preview can name a gallery section directly: arriving at a fragment held in a
    closed tab is one runtime path whichever section it names, so one arrival proves
    it, and the same page answers which tab holds every other destination. Each core
    surface then opens and shows the gallery's own content: its obligation in On Me, its
    open, resolved, and media threads in Threads, its earlier version, the other open
    page, and at phone width its Page Map. Live external data and the Threads tab's
    presets operating a sample's panel are real journeys on it too. The gallery also
    draws every kind of margin entry at once, so the same page holds the margin
    readings: the unchanged refresh watch, the margin entry atlas, and the
    rail-and-pins sample.

    One page carries all of them because opening the gallery, watched, is the suite's
    most expensive page open, which puts this test over the `browser/` tier's budget;
    how each surface behaves belongs to that surface's own tests."""
    live_leaf("second", "A second Leaf page")
    destination = "#bg-external-data"
    root = live_url(serve(FEATURE_GALLERY))
    page = open_page(browser, root + destination)
    gallery_tab = page.locator("#bg-gallery-tabs").get_by_role
    expect(gallery_tab("tab", name="Data & work")).to_have_attribute(
        "aria-selected", "true"
    )
    # The handover key is exchanged for a cookie before the address is shown.
    expect(page).to_have_url(root.split("?", 1)[0] + destination)
    expect(page.locator(":target")).to_have_attribute("id", destination[1:])
    expect(page.locator(destination)).to_be_in_viewport()

    holders = page.evaluate(
        """ids => Object.fromEntries(ids.map(id => {
          const target = document.getElementById(id);
          const panel = target?.closest('#bg-gallery-tabs > lf-tab');
          const tab = panel && document.querySelector(
            `#bg-gallery-tabs [role="tab"][aria-controls="${panel.id}"]`);
          return [id, {tag: target?.localName || null,
                       tab: tab?.textContent.trim() || null}];
        }))""",
        list(GALLERY_DESTINATIONS),
    )
    assert holders == {
        id: {"tag": "section", "tab": view} for id, view in GALLERY_DESTINATIONS.items()
    }

    links = page.get_by_role("navigation", name="On this page").get_by_role(
        "link", include_hidden=True
    )
    targets = links.evaluate_all(
        """links => links.map(link => {
          const href = link.getAttribute('href');
          const target = document.getElementById(decodeURIComponent(href.slice(1)));
          return {href, tag: target?.localName || null,
                  generated: target?.dataset.lfGen === '1'};
        })"""
    )
    assert targets[0] == {"href": "#bg-title", "tag": "hgroup", "generated": False}
    assert all(
        target["tag"] == "section" and not target["generated"] for target in targets[1:]
    ), targets
    assert len({target["href"] for target in targets}) == len(targets), targets

    # One captured source supplies a following view under its authored label.
    live = page.locator("#bg-source-live")
    original = (
        '[route]\nname = "covered terrace"\ndistance_km = 1.8\nstatus = "sample"\n'
    )
    expect(live.locator("code")).to_have_text(original)
    expect(live.locator("figcaption")).to_have_text(
        "feature-gallery-source.toml · lines 1–4"
    )
    changed = '[route]\nname = "river path"\ndistance_km = 2.1\nstatus = "updated"\n'
    page_data_model.cmd_data_set(serve.page_dir, "gallery-source", changed)
    expect(live.locator("code")).to_have_text(changed)
    expect(page.locator("#bg-measurement-guide")).to_contain_text(
        "measurement is behind its source"
    )

    # The gallery draws the margin entries the corpus has none of, and the writers that
    # only run for those are watched nowhere else: readings whose move is made wear the
    # `status` behavior on a span seat rather than a button.
    resized(page, 1440, 900)
    margins_laid_out(page)
    _refreshes_restate_no_margin_name(
        page,
        {
            ".lf-margin-cluster": 10,
            '.lf-margin-entry[data-lf-behavior="status"]': 2,
        },
    )
    _the_atlas_shows_every_margin_entry_face_in_its_treatment(page)
    _a_pin_on_a_wide_figure_hides_with_the_annotations_while_the_rail_stays(page)

    # The core chrome, each surface showing the gallery's own content.
    resized(page, 1600, 900)
    # The gallery waits on the user, so the leaf opens On Me, and its name ends in the
    # status.
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^On Me · .+ · \S")
    )
    panel_control(page, "queue").click()
    map_obligation = page.locator(".lf-fp-on-item").filter(
        has_text="Which map should the sample team carry?"
    )
    expect(map_obligation).to_have_count(1)
    expect(map_obligation).to_have_attribute("data-lf-key", "widget:bg-choice")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    gallery_tab("tab", name="Decisions").click()
    page.locator("#bg-question-api > summary").click()
    page.get_by_role("button", name="Read current obligation", exact=True).click()
    reading = json.loads(page.locator("#bg-question-reading").inner_text())
    assert reading["id"] == "widget:bg-choice"
    assert reading["source"]["id"] == "bg-choice"
    assert reading["prompt"]["target"] == "bg-choice-ask"
    assert (reading["state"], reading["next_actor"]) == ("waiting", "user")

    gallery_tab("tab", name="Threads").click()
    open_threads(page)
    expect(show_resolved(page)).not_to_have_count(0)
    media_thread = open_panel_thread(page, "2be2443f0bb6cc49fc86b52f340e6073")
    media_thread.locator(".lf-message-media").click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The Threads tab's presets each open a thread in a sample's panel, and the one
    # chosen survives its Reset.
    frame = page.frame_locator("#bg-panel-sample iframe")
    shown = frame.locator(panel_view("thread"))
    expect(shown).to_have_count(0)
    page.locator('#bg-panel-presets [data-view="overview"]').click()
    expect(shown).to_have_attribute(
        "data-lf-thread", "72e031c5bf0d485ba9054628e09869d4"
    )

    page.keyboard.press("Tab")
    you_button = page.locator('#bg-panel-presets [data-view="you"]')
    expect(you_button).to_be_focused()
    assert you_button.evaluate("element => element.matches(':focus-visible')")
    page.keyboard.press("Space")
    expect(shown).to_have_attribute(
        "data-lf-thread", "2be2443f0bb6cc49fc86b52f340e6073"
    )
    expect(you_button).to_be_focused()

    for view, thread, title in (
        ("you", "2be2443f0bb6cc49fc86b52f340e6073", "Workshop room photo"),
        ("resolved", "bab3cdfcfb8c02aacbb27da731de947a", "Projector map"),
        ("summary", "9ee465bb3f9c1fa309ea9cb1767fa365", "Afternoon workshop"),
        ("progress", "bg-progress-question", "Schedule checks"),
        (
            "overview",
            "72e031c5bf0d485ba9054628e09869d4",
            "Is lunch provided, or should attendees make their own plans?",
        ),
    ):
        page.locator(f'#bg-panel-presets [data-view="{view}"]').click()
        expect(shown).to_have_attribute("data-lf-thread", thread)
        expect(frame.locator(".lf-fp-title")).to_have_text(title)

    page.locator('#bg-panel-presets [data-view="resolved"]').click()
    expect(shown).to_have_attribute(
        "data-lf-thread", "bab3cdfcfb8c02aacbb27da731de947a"
    )
    page.locator("#bg-panel-sample").get_by_role(
        "button", name="Reset", exact=True
    ).click()
    page.locator("#bg-panel-sample").evaluate("async sample => { await sample.ready; }")
    expect(shown).to_have_attribute(
        "data-lf-thread", "bab3cdfcfb8c02aacbb27da731de947a"
    )
    # Latest commands and Reset cancel pending presentation across the port.
    result = page.locator("#bg-panel-sample").evaluate(
        """sample => Promise.all([
          sample.showThread('2be2443f0bb6cc49fc86b52f340e6073',
            {surface: 'panel', waiting: 'user'}),
          sample.showThread('bab3cdfcfb8c02aacbb27da731de947a',
            {surface: 'panel'})
        ])"""
    )
    assert result == [False, True]
    expect(frame.locator(".lf-fp-title")).to_have_text("Projector map")
    result = page.locator("#bg-panel-sample").evaluate(
        """async sample => {
          const old = sample.showThread('2be2443f0bb6cc49fc86b52f340e6073',
            {surface: 'panel', waiting: 'user'});
          await sample.reset();
          return old;
        }"""
    )
    assert result is False
    expect(frame.locator(".lf-fp-title")).to_have_text("Projector map")

    panel_control(page, "versions").click()
    expect(page.locator(".lf-fp-version").filter(has_text="v1")).to_be_visible()
    page.locator(".lf-fp-leaf").click()

    all_pages_offered(page)
    panel_control(page, "leaves", at="navigate").click()
    expect(page.locator("a.lf-fp-page")).to_contain_text("A second Leaf page")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    resized(page, 390, 900)
    page.evaluate("scrollTo(0, 0)")
    expect(page.locator("#bg-sidebar")).to_be_hidden()
    # A phone drops the contents spine out of the flow rather than stacking it above
    # the reading, so the page's first section still opens within the first screen;
    # left in the flow it lands a screen below the fold. Which section that is belongs
    # to the gallery's authored order: naming one heading here made a section added
    # above it read as a layout failure.
    expect(page.locator("#bg-view-threads > section").first).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    page_map = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(page_map).to_be_visible()
    page.keyboard.press("Escape")
    expect(page_map).to_be_hidden()


def _the_atlas_shows_every_margin_entry_face_in_its_treatment(page):
    """The atlas samples every declared behavior, tone and rank, each face in the
    treatment its state takes, and its projection through the Page Map."""
    page.locator("#bg-gallery-tabs").get_by_role("tab", name="Page & layout").click()

    atlas = page.locator("#bg-margin-controls-samples")
    expect(atlas).to_be_visible()

    def sample(name):
        return atlas.locator(f'[data-margin-entry-sample="{name}"] > .lf-margin-entry')

    for name in ("label + context", "hover or focus", "open"):
        expect(sample(name)).to_have_css("cursor", "pointer")
    for name in (
        "save",
        "cancel",
        "accept",
        "reject",
        "thread",
        "more",
        "sent",
        "waiting for delivery",
        "queued",
        "update stale",
        "turn ended",
        "glyph face",
        "count badge",
        "delivered",
        "working",
        "working · fallback",
        "resting",
        "selected",
    ):
        expect(sample(name)).to_have_css("cursor", "default")

    axes = atlas.locator(".lf-margin-entry").evaluate_all(
        """buttons => ({
          behaviors: buttons.map(button => button.dataset.lfBehavior),
          tones: buttons.map(button => button.dataset.lfTone),
          ranks: buttons.map(button => button.dataset.lfRank),
        })"""
    )
    grammar = page.evaluate(
        """async () => {
          const {CONTRIBUTION_ENTRY_SCHEMA} =
            await window.__lfCheckApi();
          return CONTRIBUTION_ENTRY_SCHEMA;
        }"""
    )
    for axis in ("behaviors", "tones", "ranks"):
        assert set(axes[axis]) == set(grammar[axis]), (
            f"the gallery shows {sorted(set(axes[axis]))} of the declared "
            f"{axis} {grammar[axis]}"
        )

    glyph = sample("glyph face")
    expect(glyph.locator(".lf-margin-entry-glyph")).to_have_text("🤔")
    count = sample("count badge")
    expect(count.locator(":scope > .lf-badges > .lf-badge-count")).to_have_text("3")
    label = sample("label + context")
    label.hover()
    preview = page.locator(PREVIEW)
    expect(preview.locator(".lf-preview-word")).to_have_text("Label + context…")
    expect(preview.locator(".lf-preview-detail")).to_have_text("Patch ready")
    page.mouse.move(0, 0)

    resting = sample("resting")
    picked_up = sample("delivered")
    working = sample("working")
    stale = sample("update stale")
    fallback = sample("working · fallback")
    expect(resting).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    expect(resting).not_to_have_attribute("data-lf-turn", re.compile(".+"))
    expect(sample("my turn")).to_have_attribute("data-lf-turn", "user")
    expect(picked_up).to_have_attribute("data-lf-agent-workflow", "delivered")
    expect(picked_up).to_have_css(
        "border-top-color",
        resting.evaluate("node => getComputedStyle(node).borderTopColor"),
    )
    expect(picked_up).to_have_css(
        "background-color",
        resting.evaluate("node => getComputedStyle(node).backgroundColor"),
    )
    expect(picked_up).to_have_css("box-shadow", "none")
    picked_up_icon = picked_up.locator(".lf-margin-entry-icon")
    expect(picked_up_icon).to_have_attribute("data-lf-icon", "comment")
    expect(picked_up_icon).to_have_css("color", token_colour(page, "--lf-accent"))
    for control in (working, fallback):
        expect(control).to_have_attribute("data-lf-agent-workflow", "working")
        expect(control).to_have_css(
            "border-top-color",
            resting.evaluate("node => getComputedStyle(node).borderTopColor"),
        )
        expect(control).to_have_css(
            "background-color",
            resting.evaluate("node => getComputedStyle(node).backgroundColor"),
        )
        expect(control).to_have_css("box-shadow", "none")
    expect(working.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "comment"
    )
    expect(fallback.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    expect(stale).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    expect(stale.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    for name, icon in (
        ("sent", "sent"),
        ("waiting for delivery", "waiting"),
        ("queued", "pickup"),
        ("turn ended", "waiting"),
    ):
        status = sample(name)
        expect(status).to_have_attribute("role", "status")
        expect(status.locator(".lf-margin-entry-icon")).to_have_attribute(
            "data-lf-icon", icon
        )
    not_selected = sample("resting")
    selected = sample("selected")
    expect(not_selected).not_to_have_attribute(
        "data-lf-target-selected", re.compile(".*")
    )
    expect(selected).to_have_attribute("data-lf-target-selected", "")
    expect(selected).to_have_css("border-top-color", token_colour(page, "--lf-ok"))
    expect(selected).to_have_css(
        "border-top-width",
        not_selected.evaluate("node => getComputedStyle(node).borderTopWidth"),
    )
    expect(selected).to_have_css("box-shadow", "none")
    expect(working.locator(".lf-margin-entry-icon")).to_have_css(
        "color", token_colour(page, "--lf-accent")
    )

    interactive = sample("hover or focus")
    interactive.hover()
    expect(interactive).to_have_css("background-color", token_colour(page, "--lf-chip"))
    expect(interactive).to_have_css(
        "border-top-color", token_colour(page, "--lf-accent")
    )
    expect(page.locator(PREVIEW)).to_be_visible()
    page.mouse.move(0, 0)
    interactive.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(interactive).to_be_focused()
    expect(interactive).to_have_css("outline-style", "solid")

    opened = sample("open")
    opened_result = atlas.locator(
        '[data-margin-entry-sample="open"] .margin-entry-gallery-disclosure'
    )
    expect(opened).to_have_attribute("aria-expanded", "true")
    expect(opened).to_have_css("border-top-color", token_colour(page, "--lf-accent"))
    expect(opened_result).to_be_visible()
    opened.click()
    expect(opened).to_have_attribute("aria-expanded", "false")
    expect(opened_result).to_be_hidden()

    projection = page.locator(
        '[data-lf-margin-for="bg-margin-controls-samples"]'
    ).get_by_role("button", name="Inspect projection", exact=True)
    expect(projection).to_be_visible()
    projection.focus()
    assert preview_parts(projection) == [
        "Inspect projection…",
        "Compact face · full row",
    ]
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    map_projection = dialog.get_by_role(
        "button", name="Inspect projection, Compact face · full row", exact=True
    )
    expect(map_projection).to_be_visible()
    expect(map_projection.locator(".lf-page-map-action-label-word")).to_have_text(
        "Inspect projection…"
    )
    expect(map_projection.locator(".lf-page-map-action-context")).to_have_text(
        "Compact face · full row"
    )
    map_projection.click()
    expect(dialog).to_be_hidden()
    expect(projection).to_have_attribute("aria-expanded", "true")
    expect(atlas.locator(".margin-entry-gallery-projection-result")).to_be_visible()


def _a_pin_on_a_wide_figure_hides_with_the_annotations_while_the_rail_stays(page):
    """The gallery's rail-and-pins sample: a comment on the schedule, which is wider
    than the column, stands on it as a pin while the prose beside it keeps the rail, and
    `g H` hides the pin while the rail stays. The quiet-status example starts with
    a visible receipt, without requiring a practice gesture to create it."""
    resized(page, 1440, 900)
    page.locator("#bg-gallery-tabs").get_by_role("tab", name="Page & layout").click()
    margins_laid_out(page)
    pin = page.locator('.lf-margin-cluster[data-lf-margin-for="bg-margin-layer-table"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    rail = page.locator('.lf-margin-cluster[data-lf-place="rail"]:visible')
    assert rail.count() > 0
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(pin).to_be_hidden()
    expect(rail.first).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(pin).to_be_visible()

    sample = page.locator("#bg-margin-layer-status")
    # The reader scrolls to the sample, whose page starts as it nears the window.
    page.mouse.move(5, 450)
    page.mouse.wheel(0, sample.bounding_box()["y"] - 100)
    expect(sample).to_be_in_viewport()
    child = sample.frame_locator("iframe")
    # The receipt reads Sent, and Waiting for delivery two minutes after the gallery
    # opened, which a slow runner can reach by now; either pins the same way.
    status = child.locator(
        '.lf-margin-entry:is([data-lf-kinds="sent"], [data-lf-kinds="waiting"])'
    )
    expect(status).to_be_visible()
    expect(status.locator("..")).to_have_attribute("data-lf-place", "pin")
    expect(child.locator(".lf-fp-leaf")).to_be_visible()
    for width in (720, 390):
        resized(page, width, 900)
        sample.scroll_into_view_if_needed()
        expect(status).to_be_visible()
        assert status.evaluate(
            """el => {
              const r = el.getBoundingClientRect();
              const board = document.querySelector('lf-board');
              return r.left >= 0 && r.right <= innerWidth && r.top >= 0
                && r.bottom <= innerHeight && board.scrollWidth <= board.clientWidth;
            }"""
        )


# The stale-keys sweep. Every control a pointer presses or typing fills, in the top
# document and its open shadow roots; live samples run their own runtime in an opaque
# frame and take no part.
_SWEPT = (
    "button, [role=button], [role=tab], [role=radio], "
    "[role=checkbox], input[type=checkbox], input[type=radio], "
    "summary, :is(textarea, input[type=search], input[type=text], "
    "input:not([type])):not(:disabled, [readonly])"
)
_FILLS = ("review", "", "a b c", "zzzz")
_SWEEP_STEPS = 40
_DESCRIBE = """element => {
  const classes = [...element.classList].slice(0, 3).map(name => `.${name}`).join('');
  const id = element.id ? `#${element.id}` : '';
  const label = (element.getAttribute('aria-label') || element.title
    || element.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
  return `${element.localName}${id}${classes} [${label}]`;
}"""
# Choose, scroll and measure in one browser task: neither a node handle nor an
# ordinal in a changing control list identifies a later pointer destination.
_SWEEP_POINT = (
    """(elements, fraction) => {
  const visible = elements.filter(element =>
    element.checkVisibility({visibilityProperty: true}));
  if (!visible.length) throw new Error('the sweep has no visible controls');
  const element = visible[Math.floor(fraction * visible.length)];
  element.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'instant'});
  const rect = element.getBoundingClientRect();
  return [Math.max(0, Math.min(innerWidth - 1, rect.x + rect.width / 2)),
          Math.max(0, Math.min(innerHeight - 1, rect.y + rect.height / 2)),
          ("""
    + _DESCRIBE
    + """)(element)];
}"""
)
_FOCUSED_INPUT = """() => {
  let element = document.activeElement;
  while (element?.shadowRoot?.activeElement) element = element.shadowRoot.activeElement;
  return element?.matches('textarea:not(:disabled, [readonly]), '
    + 'input:is([type=search], [type=text], :not([type])):not(:disabled, [readonly])');
}"""
# Each element's painted keys and availability, held in the page as a Map keyed by
# the element, so the reading after the repaint is compared node by node. Hidden
# controls have no accessible keys; a native close can hide them before its deferred
# close event refreshes their attributes. Compare the controls a reader can use.
_PAINTED_KEYS = """() => {
  const painted = new Map();
  const walk = root => {
    for (const element of root.querySelectorAll('*')) {
      if (element.checkVisibility())
        painted.set(element, [element.getAttribute('aria-disabled'),
                              element.getAttribute('aria-keyshortcuts')]);
      if (element.shadowRoot) walk(element.shadowRoot);
    }
  };
  walk(document);
  return painted;
}"""
_REPAINTED_KEYS = (
    """painted => {
  const describe = """
    + _DESCRIBE
    + """;
  const stale = [];
  for (const [element, before] of painted) {
    if (!element.isConnected) continue;
    ['aria-disabled', 'aria-keyshortcuts'].forEach((attribute, index) => {
      const now = element.getAttribute(attribute);
      if (now !== before[index])
        stale.push({element: describe(element), attribute,
                    painted: before[index], repainted: now});
    });
  }
  return stale;
}"""
)


# A press may hand an element to the browser's fullscreen, which arrives frames after
# the press and moves focus as it does, past every wait the reading takes: a reading
# it lands inside compares keys painted before the move with keys painted after it.
# The page counts the requests still unanswered, so the reading waits for the browser
# to answer each.
_FULLSCREEN_REQUESTS = """(() => {
  const request = Element.prototype.requestFullscreen;
  window.__lfFullscreenRequests = 0;
  const answered = () => window.__lfFullscreenRequests--;
  Element.prototype.requestFullscreen = function (...args) {
    window.__lfFullscreenRequests++;
    const answer = request.apply(this, args);
    answer.then(answered, answered);
    return answer;
  };
})()"""


def _stale_keys(page):
    """What a forced repaint of every element's keys changes, once the page has
    rendered what the input so far asked for: each change is an attribute that was
    stale. A control a send or a load holds unavailable is ready again once that
    finishes, so the reading waits for both: for every live sample's arrival and for
    every send to come back. The page's readiness counts what a sample's page draws
    only while its frame shows, and a Reset pressed at the window's foot can leave the
    frame below it, so the reading shows each frame still arriving out of view, as a
    check does (`start_near_work`).
    It waits too for every fullscreen request the input made, which moves focus when
    the browser answers it, and for finite motion: a closing card hides its reply box
    at the fade's end, changing which keys apply."""
    start_near_work(page)
    round_trip(page)
    page.wait_for_function("() => window.__lfFullscreenRequests === 0")
    page_at_rest(page)
    painted = page.evaluate_handle(_PAINTED_KEYS)
    # `paintKeys` reads every element's keys again (dom/keyboard/scopes.js). Saying an
    # element's commands changed reads only that element's, and `body` declares none.
    page.evaluate("async () => (await window.__lfCheckApi()).paintKeys()")
    rendered(page)
    stale = page.evaluate(_REPAINTED_KEYS, painted)
    painted.dispose()
    return stale


@pytest.mark.parametrize("example", published_sources(), ids=lambda path: path.stem)
def test_presses_and_fills_leave_no_element_naming_stale_keys(browser, serve, example):
    """Each element's `aria-keyshortcuts` and a button's `aria-disabled` reflect its
    rows, and a reflection is a tracked effect: it reads again when a signal it read
    moves. So a module's own state that a row's `when` reads must be a signal
    (`dom/keyboard/scopes.js`); a plain variable leaves the attributes stale, and a screen
    reader announces keys that no longer apply, until something else repaints them.

    The sweep presses or fills a random visible control, in an order seeded by the
    example's name, and after each step forces a repaint of every element's keys. Any
    attribute that repaint changes was stale. The keys themselves still work, since a
    press reads the rows afresh, so no other test fails on such a row. A page change
    reshuffles the steps; the failure names the step, pointer aim and typed words."""
    rng = random.Random(example.stem)
    page = open_page(browser, serve(example), init_script=_FULLSCREEN_REQUESTS)
    stale = [{"step": "arrival", **finding} for finding in _stale_keys(page)]
    for step in range(_SWEEP_STEPS):
        x, y, target = page.locator(_SWEPT).evaluate_all(_SWEEP_POINT, rng.random())
        page.mouse.click(x, y)
        did = f"press at ({x:.0f}, {y:.0f}), aimed at {target}"
        # Type through actual focus, including inside an open shadow root. A press
        # may replace the control or focus something other than the original aim.
        if page.evaluate(_FOCUSED_INPUT):
            value = rng.choice(_FILLS)
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text(value)
            did += f", fill {value!r}"
        if rng.random() < 0.15:
            page.keyboard.press("Escape")
            did += ", then Escape"
        stale += [{"step": step, "did": did, **s} for s in _stale_keys(page)]
    assert not stale, "\n".join(
        f"step {s['step']}"
        + (f" ({s['did']})" if "did" in s else "")
        + f": {s['element']} {s['attribute']} painted {s['painted']!r},"
        f" repainted {s['repainted']!r}"
        for s in stale
    )


@pytest.mark.parametrize("viewport", [(1440, 900), (390, 844)])
def test_pr_walkthrough_navigation_starts_the_review_at_every_width(
    browser, serve, viewport
):
    """Contents must be available before the reader works through this long review.

    The authored reading order puts navigation first and supporting evidence in the
    article. An outline placed after the complete PR facts and history would, when the
    tracks stack, also come after the entire article.
    """
    source = named_source("pr-walkthrough")
    url = serve(source)
    width, height = viewport
    context = browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=width < 500,
        is_mobile=width < 500,
    )
    page = open_page(browser, url, context=context)
    page.evaluate("() => document.fonts.ready")
    navigation = page.locator("#pr-contents")
    disclosure = navigation.locator("summary")
    if disclosure.is_visible() and not navigation.locator("details").evaluate(
        "node => node.open"
    ):
        disclosure.click()
    first = navigation.get_by_role("link", name="Review finding", exact=True)
    expect(first).to_be_in_viewport()
    if width < 500:
        assert (
            page.locator("#pr-contents-panel").bounding_box()["y"]
            < (page.locator("#pr-body").bounding_box()["y"])
        )

    # A real pointer press leaves the reader at a later section, with its heading
    # visible rather than under page chrome. On desktop the same outline persists.
    change = navigation.get_by_role("link", name="Change surface", exact=True)
    expect(change).to_be_in_viewport()
    change.click()
    expect(page).to_have_url(re.compile(r"#pr-change-surface$"))
    heading = page.locator("#pr-change-surface > h2")
    expect(heading).to_be_in_viewport()
    scroll_settled(page)
    assert heading.bounding_box()["y"] >= 0
    if width > 500:
        expect(first).to_be_in_viewport()

    # Begin again at the opening, and take the native tab order to another route.
    navigate(page, url)
    if disclosure.is_visible() and not navigation.locator("details").evaluate(
        "node => node.open"
    ):
        disclosure.click()
    page.evaluate(RELEASE_FOCUS)
    invariant = navigation.get_by_role("link", name="Review invariants", exact=True)
    for _ in range(30):
        page.keyboard.press("Tab")
        if invariant.evaluate("node => node.matches(':focus')"):
            break
    expect(invariant).to_be_focused()
    assert invariant.evaluate("node => node.matches(':focus-visible')")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#pr-invariants$"))
    expect(page.locator("#pr-invariants > h2")).to_be_in_viewport()
    scroll_settled(page)
    if width > 500:
        expect(first).to_be_in_viewport()


def test_target_mnemonics_filter_the_generated_map_without_renumbering_hints(
    browser, serve
):
    """Semantic prefixes narrow the current generated map instead of replacing it.

    A filtered map preserves the codes its members had in the complete map. Its chips
    show only those generated suffixes.
    """
    url = serve(
        ADDRESSED_PAGE.replace(
            '<p id="dsc-body">',
            '<p id="dsc-body"><a id="revealed-link" href="#p2">Read next passage</a> ',
        )
    )
    thread = answered_comment(
        serve.page_dir, "A visible thread.", {"section": "opts-decision"}
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")

    page.keyboard.press("?")
    goto = command_reference_rows(page, "Go to")
    filters = goto.locator(
        '[role=option][data-lf-command^="navigation.target.filter."]'
    )
    assert filters.evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          keys: [...row.querySelectorAll('kbd')].map(key => key.textContent),
          action: row.querySelector('.lf-command-reference-title-words').textContent,
        }))"""
    ) == [
        {
            "command": "navigation.target.filter.margin-entries",
            "keys": ["g", "m"],
            "action": "Show only visible margin entries",
        },
        {
            "command": "navigation.target.filter.threads",
            "keys": ["g", "t"],
            "action": "Show only visible threads",
        },
        {
            "command": "navigation.target.filter.hyperlinks",
            "keys": ["g", "h"],
            "action": "Show only visible hyperlinks",
        },
        {
            "command": "navigation.target.filter.folds",
            "keys": ["g", "f"],
            "action": "Show only visible folds",
        },
    ]
    expect(filters.locator(".lf-command-reference-description")).to_have_count(0)
    target_help = goto.locator('[role=option][data-lf-command="navigation.target"]')
    expect(target_help.locator("kbd")).to_have_text(["g", "letters"])
    expect(target_help).to_contain_text("Visible target")
    expect(target_help).not_to_contain_text("filter first")
    page.keyboard.press("Escape")

    page.keyboard.press("g")
    chips = page.locator(CHIPS)
    expect(chips.first).to_be_visible()
    initial_kinds = set(
        chips.evaluate_all("els => els.map(el => el.dataset.lfGoToKind)")
    )
    assert {"Link", "Fold", "Control"} <= initial_kinds, initial_kinds
    assert chips.evaluate_all(
        "els => els.every(el => el.textContent === el.dataset.lfHintCode)"
    ), "an inline hint repeated the sequence context"

    mixed = page.locator(
        f'{CHIPS}[data-lf-go-to-kind="Margin entry"]'
        '[data-lf-go-to-target="opts-decision"]'
    )
    expect(
        page.locator(f'{CHIPS}[data-lf-go-to-target="revealed-link"]')
    ).to_have_count(0)
    expect(mixed).to_have_count(2)
    mixed_codes = mixed.evaluate_all(
        "els => Object.fromEntries(els.map(el => "
        "[el.dataset.lfGoToMarginEntry, el.dataset.lfHintCode]))"
    )
    thread_code = mixed_codes["reading:threadList"]
    obligation_key = next(key for key in mixed_codes if key != "reading:threadList")

    page.keyboard.press("m")
    filtered = page.locator(f"{CHIPS}:visible")
    expect(filtered).to_have_count(2)
    assert address_codes(page) == list(mixed_codes.values())
    page.keyboard.press("Escape")

    page.keyboard.press("t")
    expect(filtered).to_have_count(1)
    assert address_codes(page) == [thread_code]

    page.keyboard.type(thread_code)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    page.keyboard.press("Escape")

    # Reveal another target so rearming reads a different visible scene.
    page.locator("#dsc-head").click()
    expect(page.locator("#revealed-link")).to_be_visible()
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(CHIPS).first).to_be_visible()
    assert (
        set(
            page.locator(CHIPS).evaluate_all(
                "els => els.map(el => el.dataset.lfGoToKind)"
            )
        )
        == initial_kinds
    )

    # Navigation can change the visible scene. This new map assigns its own hints;
    # filtering must preserve this map's ask code rather than the earlier map's.
    expect(
        page.locator(f'{CHIPS}[data-lf-go-to-target="revealed-link"]')
    ).to_have_count(1)
    obligation_code = address_code(
        page, "Margin entry", "opts-decision", obligation_key
    )
    page.keyboard.type(obligation_code)
    expect(page.locator("#opts-decision")).to_be_focused()
    expect(page.locator("#opts-decision")).to_have_attribute("data-lf-obligation", "1")

    # Scroll past the links to give the hyperlinks filter no members. An empty
    # filter stays empty through resize; Escape restores the complete map.
    page.locator("#opt-a").click()
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": thread},
    )
    round_trip(page)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="on-me"]')).to_have_count(0)
    # The reader scrolls there: a resize restores the reader's last chosen place, and a
    # script's scroll chooses none, so the resize would return to the click on #opt-a.
    page.mouse.move(640, 400)
    page.mouse.wheel(
        0, page.locator("#opts-decision").evaluate("node => node.offsetTop")
    )
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).not_to_be_in_viewport()
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(f"{CHIPS}:visible")).to_have_count(0)
    expect(page.locator(".lf-live")).to_have_text("No visible hyperlinks")
    expect_panel_says(page, "No visible hyperlinks")
    page.evaluate(
        """async () => {
          window.__liveChanges = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__liveChanges.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          (await window.__lfCheckApi())
            .notice('Agent replied — open Threads', {background: true});
        }"""
    )
    expect(page.locator(".lf-live")).to_have_text("Agent replied — open Threads")
    # The empty filter's word stands in the panel while Go-to does; the news waits.
    assert "No visible hyperlinks" in panel_says(page)
    assert "Agent replied" not in panel_says(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(".lf-live")).to_have_text(
        "No hint d. The current hints are unchanged."
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    resized(page, 1200, 800)
    expect_panel_says(page, "No visible hyperlinks")
    expect(page.locator(f"{CHIPS}:visible")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS).first).to_be_visible()
    expect(page.locator(".lf-live")).to_have_text("All go-to targets.")
    # Once Escape clears the filter's word, the waiting news takes the panel's seat
    # after the notices queued ahead of it retire. The live region speaks
    # announcements in the order they are made, so the next Escape's word arrives
    # after any announcement made as the news showed.
    expect_panel_says(page, "Agent replied — open Threads")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-live")).to_have_text("Go to cancelled")
    assert (
        page.evaluate(
            "() => window.__liveChanges.filter(words => "
            "words === 'Agent replied — open Threads').length"
        )
        == 1
    ), "showing deferred news announced it a second time"

    # The obligation route may scroll these hyperlinks out of the visible target map.
    page.keyboard.press("Escape")
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("h")
    links = page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')
    expect(links).to_have_count(3)
    expect(
        page.locator(f'{CHIPS}:visible:not([data-lf-go-to-kind="Link"])')
    ).to_have_count(0)
    resized(page, 1180, 800)
    expect(links).to_have_count(3)
    expect(
        page.locator(f'{CHIPS}:visible:not([data-lf-go-to-kind="Link"])')
    ).to_have_count(0)
    page.keyboard.type(address_code(page, "Link", "lk2"))
    page.wait_for_url(re.compile(r"#p2$"))
    expect(page.locator("#p2")).to_be_focused()


def test_the_g_chord_reaches_named_surfaces_and_visible_targets(browser, serve):
    """Mnemonics reach global surfaces; generated hints reach the visible scene.

    The panel's Threads and On Me, the Page Map dialog, and page edges keep stable
    named routes. Margin entries,
    tabs, links, folds, and the presses a widget built instead share one viewport-local
    letter namespace."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    comment({"quote": "passage under discussion"}, "Sharpen this.")
    comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")
    page = open_page(browser, url)
    expect_open_threads(page, 3)
    resized(page, 1280, 800)

    # The complete reference shows each command once, preferring an executable intrinsic
    # route over its contextual Go-to route. Keep identities across all sections so that
    # a command such as Align current item can be covered by its permanent page route.
    page.keyboard.press("?")
    goto = command_reference_rows(page, "Go to")
    reference_commands = set(
        page.locator(
            ".lf-command-reference [role=option][data-lf-command]"
        ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    )
    alignment = page.locator(
        '.lf-command-reference [role=option][data-lf-command="reading.align.top"]'
    )
    expect(alignment).to_have_count(1)
    # Alignment has a page-level route even when no reading item stands while
    # the reference opens from chrome.
    expect(alignment.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "z"])
    overlaps = goto.locator("[role=option][data-lf-command]").evaluate_all(
        """rows => rows.flatMap(row => {
          const key = row.querySelector('.lf-command-reference-key')
            .firstElementChild.getBoundingClientRect();
          const action = row.querySelector('.lf-command-reference-action')
            .getBoundingClientRect();
          const across = Math.min(key.right, action.right) - Math.max(key.left, action.left);
          const down = Math.min(key.bottom, action.bottom) - Math.max(key.top, action.top);
          const amount = Math.min(across, down);
          return amount > 0.5 ? [{command: row.dataset.lfCommand, amount}] : [];
        })"""
    )
    assert overlaps == [], f"a complete route overlaps its action: {overlaps}"
    page.keyboard.press("Escape")

    # Armed, the live Go to register's commands are all in the complete reference.
    page.keyboard.press("g")
    live_commands = set(
        page.evaluate(
            """async () => {
              const {pageScopes} = await window.__lfCheckApi();
              const {live, commandPresentations} = await window.__lfCheckApi();
              const scope = pageScopes().find(scope => scope.rows?.some(
                row => row.id === 'navigation.target'));
              return scope.rows.filter(live).flatMap(row =>
                commandPresentations(row).map(({id}) => id));
            }"""
        )
    )
    assert live_commands, "the page must contribute live Go to commands"
    assert live_commands <= reference_commands, (
        f"live Go to commands missing from the complete reference: "
        f"{sorted(live_commands - reference_commands)}"
    )
    assert "navigation.panel.leaves" not in reference_commands
    expect(page.locator(CHIPS).first).to_be_visible()
    # The chips are the eye's copy of the Go-to sequence; a user who cannot see them is
    # told the window opened and what it holds.
    expect(page.locator(".lf-live")).to_contain_text("visible targets")
    expect(page.locator(".lf-live")).to_contain_text("letters visible target")

    # A panel mnemonic completes the sequence and leaves the user on that view's first
    # row, where its own scoped keys are immediately available.
    threads = page.locator(panel_view("threads"))
    page.keyboard.press("Shift+t")
    expect(threads.locator(".lf-fp-thread").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # The On Me sequence follows the same contract: the view opens on its first card.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    expect(page.locator(".lf-fp-on-item").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)

    # Replacing one view with another is lateral: Threads replaces On Me while it
    # stands, and the Escape out of Threads lands on the page rather than putting On Me
    # back.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # Page Map stands over whatever the user already had, so closing it leaves On Me
    # where it was.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status or location in Page Map"
        )
    ).to_be_focused()
    # Its accessible name does not add a second visible caption above the placeholder.
    assert (
        sheet.locator(".lf-page-map-search").evaluate(
            "node => node.shadowRoot.querySelector('[part~=form-control-label]')"
            ".getBoundingClientRect().height"
        )
        <= 1
    )
    page.evaluate(
        """() => {
          window.__lfPageMapClosed = false;
          document.querySelector('dialog.lf-page-map-dialog').addEventListener(
            'close',
            () => { window.__lfPageMapClosed = true; },
            {once: true},
          );
        }"""
    )
    page.keyboard.press("Escape")
    page.wait_for_function("() => window.__lfPageMapClosed")
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "queue")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # Uppercase M opens the complete Page Map rather than the numbered prefix.
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-group")).not_to_have_count(0)
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status or location in Page Map"
        )
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()

    # A visible Margin entry shares the generated target map. Activating the hint
    # opens the same thread preview as its marker. Each quoted passage in p1 stands its
    # own entry, so the walk takes the first.
    page.keyboard.press("g")
    entries = page.locator(
        f'{CHIPS}[data-lf-go-to-kind="Margin entry"][data-lf-go-to-target="p1"]'
    )
    expect(entries).to_have_count(2)
    page.keyboard.type(entries.first.get_attribute("data-lf-hint-code"))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread .lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    # The hyperlinks, from the head of the page where both are on screen. A hint is centred on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # route's visible start rather than on the inline's wide union box.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')).to_have_count(2)
    assert page.evaluate(
        """() => {
             const links = [...document.querySelectorAll('#refs a[href]')];
             const chips = links.map(link => document.querySelector(
               `.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-target="${link.id}"]`));
             return {wrapped: links[0].getClientRects().length > 1,
                     on: chips.map((chip, i) => {
                       const c = chip.getBoundingClientRect();
                       const first = links[i].getClientRects()[0];
                       return Math.abs(c.left + c.width / 2 - first.left) < 2
                           && Math.abs(c.top + c.height / 2 - first.top) < 2;
                     })};
           }"""
    ) == {
        "wrapped": True,
        "on": [True, True],
    }, "a chip is not on the corner its link starts at"
    page.keyboard.press("Escape")

    # At the foot of the page neither hyperlink is visible, so neither receives a route.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # A resolved thread is the panel's state rather than an authored fold. Read of the
    # document at large, `f` must not offer a digit for it.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect_open_threads(page, 2)
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Fold"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # The folds, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the user
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    fold_code = address_code(page, "Fold", "dsc-head")
    assert page.evaluate(
        """() => {
             const c = document.querySelector(
               '.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-target="dsc-head"]')
                        .getBoundingClientRect();
             const words = document.createRange();
             words.selectNodeContents(document.getElementById('dsc-head'));
             const first = words.getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.top + c.height / 2 - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary's words start at"
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.type(fold_code)
    expect(page.locator("#dsc-head")).to_be_focused()
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # Located there, Enter and Space both toggle it, as a summary answers both.
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # A press a widget built joins the same namespace, declared by the constructor that
    # made it rather than by an entry here. A pick spends no page letter of its own — the
    # register holds capabilities, and a control is a route to one — so without that
    # declaration the only keyboard way to it would be Tab. The arrival is the press, so
    # the option is chosen.
    page.evaluate(
        """() => document.scrollingElement.scrollTo(
             0, document.getElementById('opts-decision').offsetTop - 80)"""
    )
    page.keyboard.press("g")
    controls = page.locator(f'{CHIPS}[data-lf-go-to-kind="Control"]')
    expect(controls).not_to_have_count(0)
    pick_code = page.evaluate(
        """() => {
             const mark = document.querySelector('#opt-a .lf-pick').getBoundingClientRect();
             const chip = [...document.querySelectorAll(
               '.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-kind="Control"]')]
               .find(c => {
                 const r = c.getBoundingClientRect();
                 return Math.abs(r.left + r.width / 2 - mark.left) < 2
                     && Math.abs(r.top + r.height / 2 - mark.top) < 2;
               });
             return chip ? chip.dataset.lfHintCode : null;
           }"""
    )
    assert pick_code, "the pick mark the widget built got no Go-to hint"
    page.keyboard.type(pick_code)
    expect(page.locator("#opt-a")).to_have_attribute("selected", "")

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key completes the route — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.scrollingElement.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.scrollingElement.scrollTop === 0")

    # A panel mnemonic completes the sequence directly wherever the user is on the page.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(threads.locator(".lf-fp-thread").first).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # Typing contexts are untouched: in a box, the whole sequence is text.
    page.keyboard.press("c")
    box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    expect(box).to_be_focused()
    page.keyboard.type("gc1")
    expect(box).to_have_js_property("value", "gc1")
    expect(box).to_be_focused()


def test_the_pr_walkthrough_exercises_an_inline_diff_thread(browser, serve):
    """The diff package's worked page carries a real line thread through both seats."""
    source = named_source("pr-walkthrough")
    url = live_url(serve(source))
    page = open_page(browser, url)
    diff = page.locator("#pr-exact-patch")
    details = diff.locator(".lf-diff-file > details").first
    details.evaluate("element => { element.open = true; }")
    target = details.locator("[data-line-type='change-addition'][data-lf-datum]").first
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this review note beside the line that changes it.",
            "anchor": {
                "section": "pr-exact-patch",
                "datum": target.get_attribute("data-lf-datum"),
                "source": target.get_attribute("data-lf-source"),
                "source_revision": target.get_attribute("data-lf-source-revision"),
            },
        },
    )
    told(page)
    thread = diff.locator(f'.lf-page-thread[data-lf-thread="{root["id"]}"]')
    expect(thread).to_contain_text(
        "Keep this review note beside the line that changes it."
    )
    send = thread.locator(".lf-compose-submit")
    expect(send).to_be_disabled()
    expect(text_field(thread, name="Reply", exact=True)).to_be_visible()
    markers = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    baseline = markers.count()

    details.evaluate("element => { element.open = false; }")
    expect(thread).to_have_count(0)
    expect(markers).to_have_count(baseline + 1)
    details.evaluate("element => { element.open = true; }")
    expect(thread).to_have_count(1)
    expect(markers).to_have_count(baseline)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    # A thread the margin projects, standing before the diff in page order: the walk
    # opens the margin's view to reach it and then steps on to the diff's own seat,
    # closing that view on the way. The walk moves the user laterally rather than down
    # a level, so Escape lets go of the thread they ended on and lands them in the page
    # where they now are — not back at the heading the walk started from, which is
    # off screen by then.
    prose = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "And one on the prose above the patch.",
            "anchor": {"section": "pr-scale-intro", "quote": "Risk is concentrated"},
        },
    )
    told(page)
    heading = page.locator("main h2").first
    heading.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(heading).to_be_focused()
    page.keyboard.press("t")
    expect(
        page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{prose["id"]}"]'
        )
    ).to_be_focused()
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_thread_walk_card_leaves_and_returns_with_its_anchor(browser, serve):
    """A contextual thread has one side, and leaves and returns with its anchor."""
    page = open_page(
        browser,
        live_url(serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)),
    )
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("t")
    card = page.locator(".lf-margin-preview")
    # Whichever thread the walk reaches first; the page's order decides that.
    expect(card.locator(".lf-page-thread")).to_be_focused()
    walked = card.locator(".lf-page-thread").get_attribute("data-lf-thread")
    owner = page.locator(
        '.lf-margin-marker[data-lf-kinds~="comment"]'
        '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
    ).locator("xpath=..")
    expect(owner).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    initial = owner.bounding_box()
    assert initial["y"] + initial["height"] > 50
    assert initial["y"] < 900
    page.evaluate("distance => scrollBy(0, distance)", min(160, initial["y"] - 80))
    page.wait_for_function(
        """() => {
          const owner = document.querySelector(
            '.lf-margin-marker[data-lf-kinds~="comment"]' +
            '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
          )?.parentElement?.getBoundingClientRect();
          return owner && owner.bottom > 50 && owner.top < innerHeight;
        }"""
    )
    expect(card).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    # Scrolled away, the card leaves with its anchor rather than closing, and scrolled
    # back it stands where it stood, with the user still in it.
    rendered(page)
    placed = card.evaluate("node => node.getBoundingClientRect().top")
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    rendered(page)
    assert card.evaluate("node => node.getBoundingClientRect().bottom <= 0")
    page.evaluate("top => scrollTo(0, top)", before)
    rendered(page)
    assert card.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        placed, abs=0.5
    )
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{walked}"]')).to_be_focused()
    # A press the page answers leaves the window where the user put it: `g G` carries the
    # card away, and `g` then opens Go-to over the page's foot rather than bringing the
    # card back and mapping the window around it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+g")
    rendered(page)
    foot = page.evaluate("() => document.scrollingElement.scrollTop")
    assert card.evaluate("node => node.getBoundingClientRect().bottom <= 0")
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    # Every key is Go-to's while it stands, one it has no use for included: that key
    # takes Go-to down and keeps the page where it is.
    page.keyboard.press("F2")
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    # A turn arriving in the card is news, not a move of the user's: it stays away.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": walked,
            "revision": 1,
            "text": "A turn arriving while the card is away.",
        },
    )
    told(page)
    expect(card).to_contain_text("A turn arriving while the card is away.")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    shown = """() => {
      const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
      return card.top >= 0 && card.bottom <= innerHeight;
    }"""
    # The `g` that opened Go-to let go of the card it was pressed in, scrolled away
    # there, so a page command acts from what the user sees: `c` opens the page's own
    # field rather than the card's reply, and the card stays where the page took it.
    page.keyboard.press("c")
    reply = text_field(card, name="Reply", exact=True)
    expect(page.locator(".lf-fp-field leaf-text")).to_be_focused()
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    assert not page.evaluate(shown)
    page.keyboard.press("Escape")
    # Back at the card, a click on its words puts the user in it again, and `c` replies
    # there.
    page.evaluate("top => scrollTo(0, top)", before)
    rendered(page)
    card.locator(".lf-page-thread .lf-msg-body").first.click()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.wait_for_function(shown)
    # A field keeps its keys scrolled away, since typing brings its box back, so Tab
    # moves on from the reply to the card's next control, which the browser reveals.
    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    rendered(page)
    assert not page.evaluate(shown)
    page.keyboard.press("Tab")
    expect(reply).not_to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.closest('.lf-margin-preview') !== null"
    )
    page.wait_for_function(shown)
    # A card the page has carried half past the window's top, Reply with it, is as
    # unseen there as one scrolled off: a landing in it brings it back all the same.
    # The box goes more than the pixel of slack past the top that reads a card held
    # flush at the edge as shown (readings/off-flow.js, `unseen`).
    reply.evaluate(
        """async (box) => {
          const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          while (box.getBoundingClientRect().top >= -1) {
            scrollBy(0, 10);
            await frame();
          }
        }"""
    )
    rendered(page)
    assert page.evaluate(
        "() => document.querySelector('.lf-margin-preview').getBoundingClientRect().bottom > 0"
    )
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.wait_for_function(shown)
    # A click from the card's thread into its Reply, cut off at the window's top, leaves
    # the page and the box under the pointer still: the pointer found the box where it
    # is. The first word typed there brings the card back, as a browser brings a field
    # back for its caret.
    page.keyboard.press("Escape")
    expect(card.locator(".lf-page-thread")).to_be_focused()
    reply.evaluate(
        """async (box) => {
          const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          while (box.getBoundingClientRect().top >= 0) {
            scrollBy(0, 2);
            await frame();
          }
        }"""
    )
    rendered(page)
    pressed = reply.bounding_box()
    assert pressed["y"] < 0 < pressed["y"] + pressed["height"] - 8
    held = page.evaluate("() => document.scrollingElement.scrollTop")
    page.mouse.click(
        pressed["x"] + pressed["width"] / 2, pressed["y"] + pressed["height"] - 6
    )
    expect(reply).to_be_focused()
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == held
    assert reply.bounding_box()["y"] == pytest.approx(pressed["y"], abs=0.5)
    page.keyboard.type("S")
    page.wait_for_function(
        "() => document.querySelector('.lf-margin-preview leaf-text')"
        ".getBoundingClientRect().top >= 0"
    )


def test_an_addressed_link_leaves_the_user_at_its_destination(
    browser, serve, other_leaf, one_user
):
    """A generated link hint completes the navigation step it names.

    A fragment lands focus on its target, so the user does not remain at the place they
    left. A link its author sends to a new tab opens there and names that context change
    even though the sequence activates the link without first moving focus through
    it."""
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={server_model.host_key()}"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "addressed links",
                f"""
<h1>Addressed links</h1>
<p><a id="internal" href="#arrival">Read the conclusion</a>.</p>
<p><a id="external" href="{destination}" target="_blank" aria-label="Leaf guide"
  >Open the guide</a>.</p>
<div style="height: 1600px"></div>
<h2 id="arrival">Conclusion</h2>
<p>The internal navigation step ends here.</p>
""",
            )
        ),
        context=one_user,
    )

    go_to_address(page, "Link", "internal")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator("#arrival")).to_be_in_viewport()
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )

    page.keyboard.press("g")
    external_code = address_code(page, "Link", "external")
    tab = opened_tab(page, destination, lambda: page.keyboard.type(external_code))
    expect(tab).to_have_url(f"{other_url}/")
    expect(page.locator(".lf-live")).to_have_text("Opened Leaf guide in a new tab")


def test_an_external_link_wears_its_mark_and_opens_where_its_author_says(
    browser, serve, other_leaf, one_user
):
    """A link that leaves the page wears the mark after it and keeps the attributes its
    author wrote, so with no `target` it opens in the page's own tab."""
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={server_model.host_key()}"
    url = serve(
        leaf_page(
            "external link",
            f"""
<h1 id="top">Links</h1>
<p>Read the <a id="external" href="{destination}" aria-label="other leaf documentation"
  aria-describedby="source-note">other leaf</a>.</p>
<span id="source-note" hidden>curated source</span>
<p>Return to <a id="fragment" href="#top">the heading</a>.</p>
<svg viewBox="0 0 40 20" aria-label="map"><a id="svg-external" href="{destination}">
  <text x="0" y="15">map</text>
</a></svg>
""",
        )
    )
    page = open_page(browser, url, context=one_user)
    external = page.locator("#external")

    expect(external).not_to_have_attribute("target", re.compile(".*"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source")
    # The mark stands inside the link, so the paragraph ends where it was written: an
    # empty inline box whose padding the icon fills (surfaces.css).
    expect(page.locator("#external ~ *")).to_have_count(0)
    expect(external).to_have_attribute("data-lf-external", "")
    mark = external.evaluate("""link => {
      const style = getComputedStyle(link, '::after');
      return {display: style.display, room: parseFloat(style.paddingInlineStart),
        mask: style.maskImage};
    }""")
    assert mark["display"] == "inline"
    assert mark["room"] > 0
    assert "data:image/svg+xml" in mark["mask"]
    expect(page.locator("#fragment")).not_to_have_attribute("data-lf-external", "")
    expect(page.locator("#svg-external")).not_to_have_attribute("data-lf-external", "")

    external.click()
    expect(page).to_have_url(f"{other_url}/")
