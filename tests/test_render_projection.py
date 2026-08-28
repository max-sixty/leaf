"""Live version, report, replay, and projection tests."""

import json
import re
import threading
import time
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import render_checks as render_checks_model
from leaf import rendering as rendering_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import validation as validation_model
from playwright.sync_api import expect
from render_support import (
    ASKS_IN_ORDER,
    ASKS_PAGE,
    BOTH_STAMPS,
    BOXLESS_SECTION_PAGE,
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PACKAGE,
    COMMAND_HUB_PAGE,
    IMPORTER_CARD,
    KEPT_SECTION_PAGE,
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    MARKDOWN_REPLY,
    REF_PAGE,
    RELATIVE_WIDGET_MODULE,
    RELATIVE_WIDGET_PAGE,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    REPORT_PAGE,
    RETIRED_WIDGET_PAGE,
    RING,
    ROSTER_PAGE,
    SCROLL_SETTLE_MS,
    SCROLL_SETTLED,
    SPECIMEN_MARKUP,
    SPECIMEN_TEXT,
    STANDING_ACTIONS,
    STANDING_PAGE,
    SUGGESTION_PAGE,
    THREAD_ASKS,
    TOKEN,
    TRAVEL_PAGE,
    TWO_HOLDER_PAGE,
    TWO_HOLDER_SPARE_PAGE,
    WRAP_TOP,
    _until,
    actions,
    author_test_widget,
    backdate_note,
    compare_with,
    composer_quote,
    drifting_widget,
    leaf_page,
    live_url,
    open_page,
    opened_tab,
    page_registry,
    painted,
    panel_settled,
    refuse,
    resized,
    round_trip,
    stale_report,
    stamp_page,
    stamp_version_file,
    ticked,
    token_colour,
    told,
    trial_family,
    undo,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly


def test_the_live_page_adopts_a_revision_and_stamps_it_without_replacing_main(
    browser, serve
):
    """A valid save advances the live surface; stamping only changes its label.

    The next file is fetched while the reader keeps this document, then its authored
    main replaces the old one and replay catches it up. The URL, runtime identity, open
    chrome, and passage's viewport coordinate therefore survive. Five paragraphs arrive
    above that passage so a raw scroll offset cannot satisfy the position assertion.
    """
    version_url = serve(LIVE_V1)
    page, errors = open_page(browser, live_url(version_url))
    assert "/versions/" not in page.url, f"the live address redirected to {page.url}"

    page.locator("#live-reading").scroll_into_view_if_needed()
    page.evaluate(
        """() => { document.body.scrollBy({
          top: document.getElementById('live-reading').getBoundingClientRect().top - 140,
          behavior: 'instant'
        }); window.__leafDocument = 'the same runtime'; }"""
    )
    before = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    page.locator(".lf-comments").click()
    panel_settled(page)

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")

    assert page.evaluate("window.__leafDocument") == "the same runtime", (
        "the version replaced the browser document rather than its authored page"
    )
    assert "/versions/" not in page.url, (
        f"the update changed the live address to {page.url}"
    )
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    after = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(after - before) <= 4, (
        f"the passage moved from {before}px to {after}px in the viewport"
    )
    expect(page.locator(".lf-version")).to_contain_text("Draft after v1")
    expect(page.locator(".lf-signoff")).to_have_count(0)
    assert page.locator('meta[name="description"]').get_attribute("content") == "second"
    assert page.locator("html").get_attribute("lang") == "fr"
    assert page.locator("html").get_attribute("data-live-root") == "second"
    expect(page.locator("body")).to_have_class(re.compile(r"\blive-second\b"))
    assert page.locator("body").get_attribute("data-live-body") == "second"
    assert (
        page.locator("body").evaluate(
            "el => el.style.getPropertyValue('--live-body').trim()"
        )
        == "2"
    ), "the new version's authored root attributes did not activate"
    assert (
        page.locator("#live-reading").evaluate(
            "el => getComputedStyle(el).getPropertyValue('--live-cut').trim()"
        )
        == "2"
    ), "the new version's page-local style did not activate"

    page.evaluate("window.__leafMain = document.querySelector('main')")
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["version", "stamp", str(serve.page_dir), "--text", "new findings"],
    )
    assert stamped.exit_code == 0, stamped.output
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    expect(page.locator(".lf-signoff")).to_be_visible()
    assert page.evaluate("window.__leafMain === document.querySelector('main')"), (
        "stamping the displayed revision replaced its main"
    )

    page.locator(".lf-general textarea").fill("This comment belongs to the live draft.")
    page.locator(".lf-general button").click()
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["revision"] == 2
    assert errors == []
    page.close()


def test_a_stamped_url_stays_pinned_while_the_live_root_follows_a_draft(browser, serve):
    version_url = serve(LIVE_V1)
    pinned, pinned_errors = open_page(browser, version_url)
    live, live_errors = open_page(browser, live_url(version_url))

    (serve.page_dir / "index.html").write_text(LIVE_V2.replace("</main>", ""))
    told(live)
    told(pinned)
    expect(live.locator(".lf-latest-chip")).to_contain_text(
        "Latest edit couldn't be shown"
    )
    expect(pinned.locator(".lf-latest-chip")).not_to_contain_text(
        "Latest edit couldn't be shown"
    )
    expect(live).to_have_title("Live first")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(live)
    told(pinned)

    expect(live).to_have_title("Live second")
    expect(live.locator(".lf-version")).to_contain_text("Draft after v1")
    expect(pinned).to_have_title("Live first")
    expect(pinned).to_have_url(re.compile(r"/versions/v1\.html"))
    expect(pinned.locator(".lf-version")).to_contain_text("v1")
    assert pinned_errors == [] and live_errors == []
    pinned.close()
    live.close()


def test_the_live_page_defers_for_typing_then_adopts_without_a_press(browser, serve):
    """Unsent words hold an arriving version, but clearing them releases it.

    The chip is news during the hold, not a required confirmation: after the reader
    leaves the textarea, the ordinary poll activates the already-published version.
    """
    version_url = serve(LIVE_V1)
    page, errors = open_page(browser, live_url(version_url))
    page.locator(".lf-comments").click()
    general = page.locator(".lf-general textarea")
    general.fill("Do not replace the page under these words.")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live first")
    expect(page.locator(".lf-latest-chip")).to_be_visible()

    # An explicit press may override the hold, but it is still an in-place activation:
    # the live address and the panel draft both survive it.
    page.locator(".lf-latest-chip").click()
    expect(page).to_have_title("Live second")
    assert "/versions/" not in page.url
    expect(general).to_have_value("Do not replace the page under these words.")

    # Keep editing after the explicit release. The chip press necessarily took focus,
    # so state the active-composition condition again before asking v3 to honor it.
    general.focus()
    expect(general).to_be_focused()
    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    expect(page).to_have_title("Live second")

    general.fill("")
    page.locator("#live-reading").click()
    told(page)
    expect(page).to_have_title("Live third")
    assert "/versions/" not in page.url
    expect(page.locator(".lf-signoff")).to_have_count(0)
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blive-second\b"))
    assert page.locator("body").get_attribute("data-live-body") is None
    assert (
        page.locator("body").evaluate(
            "el => el.style.getPropertyValue('--live-body').trim()"
        )
        == ""
    ), "the retired version's authored inline property survived"
    assert page.locator("body").evaluate(
        "el => el.style.getPropertyValue('--lf-head').trim()"
    ), "activation erased a runtime-owned root property"
    assert page.locator('meta[name="description"]').get_attribute("content") == "third"
    assert errors == []
    page.close()


def test_overlapping_state_answers_share_one_live_version_activation(browser, serve):
    """Two ordinary polls cannot replace the main twice.

    Hold the shared version-file request past one polling interval, so a second timer
    response joins the first while both await that document. One transition proves the
    serialization is at the commit boundary, after asynchronous preparation, rather than
    only before it.
    """
    page, errors = open_page(browser, live_url(serve(LIVE_V1)))
    page.evaluate(
        """() => {
          const start = document.startViewTransition.bind(document);
          window.__leafTransitions = 0;
          document.startViewTransition = update => {
            window.__leafTransitions += 1;
            return start(update);
          };
        }"""
    )

    def slow_version(route):
        time.sleep(3)
        route.continue_()

    page.route("**/revisions/r2-*.html", slow_version)
    (serve.page_dir / "index.html").write_text(LIVE_V2)

    expect(page).to_have_title("Live second", timeout=10_000)
    assert page.evaluate("window.__leafTransitions") == 1
    assert errors == []
    page.close()


def test_a_skipped_transition_lands_the_version_without_a_fault(browser, serve):
    """A skipped view transition still runs its update, but it rejects `ready`, which
    the activation never awaits. Unhandled, that rejection reached the page's error
    report, and every version landing in a hidden tab wrote an `error` event into
    the log. The harness cannot hide a document, so the skip is invoked directly; it
    is the same algorithm a hidden document runs.
    """
    page, errors = open_page(browser, live_url(serve(LIVE_V1)))
    page.evaluate(
        """() => {
          const start = document.startViewTransition.bind(document);
          document.startViewTransition = update => {
            const transition = start(update);
            transition.skipTransition();
            return transition;
          };
        }"""
    )
    (serve.page_dir / "index.html").write_text(LIVE_V2)

    # The rejection is dispatched before the skipped update runs as its own task, so
    # a landed version is the edge after which the report would already be written.
    expect(page).to_have_title("Live second", timeout=10_000)
    assert errors == []
    page.close()


def test_the_ask_walk_keeps_its_place_when_a_version_lands(browser, serve):
    """An immutable version follows by navigation, and the reader's place rides across.
    The passage they were reading did; where the walk had got to was a variable in a
    module the navigation threw away, so it did not, and the reader was demoted without
    a word from the most exact reading of where they stand to the coarsest. Standing on
    the third of four asks when v2 landed, they pressed `n` and were handed the third
    again — after looking slightly back above that Ask, the block at the top of the
    window is somewhere they had already walked past.

    So the walk's place travels in the same record as the passage, and the press after
    the version lands is the press they would have made before it. The ring does not
    travel and is not owed a record: it is painted from the focus, and a reader arriving
    at a fresh document is standing on the page rather than in the ask they left."""
    url = serve(ASKS_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    # Short enough that an ask in the middle of the window has page text above it,
    # which is the whole of what makes the coarse reading the wrong one.
    resized(page, 900, 400)

    for ask in ASKS_IN_ORDER[:3]:
        page.keyboard.press("n")
        expect(page.locator(f"#{ask}")).to_have_attribute("data-lf-ask", "1")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    # Ask travel now starts at the Ask's opening, which normally makes the coarse
    # reading agree with the saved landing. Look back just far enough to make the two
    # meanings diverge: the scroll position says the preceding change, while the walk's
    # exact record still says the third Ask.
    page.evaluate("""() => {
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        document.body.scrollBy({top: earlier.bottom - 80, behavior: 'instant'});
    }""")

    stamp_page(d, ASKS_PAGE, "two")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)

    expect(page.locator("[data-lf-ask]")).to_have_count(0)
    # The condition the restore is for, stated rather than assumed: an earlier ask's own
    # prose is on screen above the one the reader was standing on, so a walk reading the
    # page alone starts behind them and steps forward onto the ask they just left.
    assert page.evaluate("""() => {
        const ask = document.getElementById('t-baffles').getBoundingClientRect();
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        return earlier.bottom > 42 && earlier.bottom <= ask.top;
    }"""), "the reader is at the top of the window, where either reading would do"
    page.keyboard.press("n")
    expect(page.locator("#t-bath")).to_have_attribute("data-lf-ask", "1")
    assert errors == []
    page.close()


def test_the_reading_position_restores_onto_a_section_that_draws_no_box(browser, serve):
    """The landmark a reading position falls back to is an element like any other, and
    an element that generates no box measures (0,0) at the document's origin.

    Read raw, that answer arrives on both sides of the subtraction — once when the
    place is written down and once when it is put back — so the correction came out 0
    and a restore that had somewhere to land did nothing at all. The reader was left at
    the top of a page they had been thirty paragraphs into. It is quiet twice over: only
    a reader whose quote the new version rewrote reaches this branch, and a page whose
    sections all draw boxes never sees it."""
    url = serve(BOXLESS_SECTION_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    resized(page, 900, 600)

    # Read from inside the wrapper, so every block on screen is one of its own and the
    # nearest id above them is the wrapper.
    page.evaluate("""() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('wrap'));
      document.body.scrollTop += r.getBoundingClientRect().top + 50; }""")
    before = page.evaluate(WRAP_TOP)

    # The branch under test, stated rather than assumed. In-place activation carries this
    # object directly; pagehide stores the same capture for document travel, which gives
    # the test a view of it without adding a second diagnostic representation.
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate("""() => {
      for (const k of Object.keys(sessionStorage))
        if (k.endsWith('lf-view')) return JSON.parse(sessionStorage[k]);
      return null; }""")
    assert view and view["section"] == "wrap", (
        f"the landmark was not the boxless wrapper: {view}"
    )
    assert view["quote"].startswith("Held"), (
        f"v2 still holds this quote, so the section branch never ran: {view}"
    )

    stamp_page(d, KEPT_SECTION_PAGE, "two")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)

    after = page.evaluate(WRAP_TOP)
    assert abs(after - before) <= 4, (
        f"the reader left the wrapper's words {before}px from the top of the window and "
        f"was put back at {after}px"
    )
    assert errors == []
    page.close()


def test_the_ring_says_where_the_reader_is_standing(browser, serve):
    """One ring, meaning one thing: this is where the reader is standing. It is painted
    from the focus, so every way into an ask paints it and leaving takes it off.

    The walk used to write it, and nothing ever took it off. So it said where the walk
    had left them rather than where they were: press `n`, click away, work in the panel
    for ten minutes, and an ask nobody was standing in went on wearing "you are here" —
    while a reader who had reached the same ask by Tab or by clicking one of its
    controls got no ring at all. The same place, marked or not by how they arrived.

    The chrome wears the same band, because a reader who has backed out of the panel is
    standing on a button and that is the same fact about them. It wore the browser's own
    ring there, in the browser's blue, a few inches from an ask ringed in the page's
    accent, with nothing saying the two rectangles meant one thing."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    question = page.locator("#live-question")
    page.keyboard.press("n")
    expect(question).to_have_attribute("data-lf-ask", "1")
    ask_ring = question.evaluate(RING)
    assert ask_ring == [
        "solid",
        "2px",
        token_colour(page, "--accent"),
    ], f"the ask is not ringed in the page's own band: {ask_ring}"

    # A suggestion hangs its ✓ Accept out in the page margin and the focus lands on
    # it, so this arrival paints two marks for one fact — the ring on the change, the
    # focus band on the pill deciding it — and they had better be one band. The pill's
    # comes from the runtime's own .lf-pill rule, which every press in that margin
    # wears: the suggestion family spelled its own once, which is a family stating a
    # fact about a shape the runtime owns.
    page.keyboard.press("n")
    accept = page.locator(".lf-sug-accept")
    expect(accept).to_be_focused()
    assert accept.evaluate(RING) == ask_ring, (
        "the control in the margin is drawn in some other band than the ask it decides: "
        f"{accept.evaluate(RING)} against {ask_ring}"
    )

    # Standing somewhere that asks nothing takes it off, rather than leaving it behind.
    page.locator("#h").click()
    expect(page.locator("[data-lf-ask]")).to_have_count(0)

    # A pointer landing inside an open ask is standing in it, though no walk brought
    # them there: the ring renders the focus rather than remembering a press.
    page.locator("#live-question textarea").click()
    expect(question).to_have_attribute("data-lf-ask", "1")

    # Answering takes it off with the focus still inside: the ring is for the question
    # the reader is working, and an answered one is no longer a question. Answering is
    # what does this — leaving the reader's list does not, so a widget waiting on the
    # agent in its own seat keeps the ring while the count drops.
    page.locator("#lq-token .lf-pick").click()
    expect(page.locator(".lf-asks")).to_have_text("Asks (3)")
    expect(page.locator("[data-lf-ask]")).to_have_count(0)
    expect(page.locator("#lq-token .lf-pick")).to_be_focused()

    # The chrome's own control, reached the way the ladder lands a reader on it: opened
    # by pointer, closed by key, which is what earns the ring at all.
    toggle = page.locator(".lf-comments")
    toggle.click()
    page.keyboard.press("Escape")
    expect(toggle).to_be_focused()
    assert toggle.evaluate(RING) == ask_ring, (
        "the reader standing in the chrome is drawn in some other band than the "
        f"one an ask uses: {toggle.evaluate(RING)} against {ask_ring}"
    )
    assert errors == []
    page.close()


def test_escape_lets_go_of_the_ask_the_reader_is_standing_on(browser, serve):
    """The ladder unwinds from where the reader is, and out on the page the innermost
    thing they are in is the ask they are standing on. There was no rung for it: `n`
    brought them to an ask, ringed it, and no key took them out again — the one place in
    the runtime where a press put the reader somewhere with nothing to undo it, and the
    line said nothing about Escape at all while they stood there.

    What letting go is not is the walk forgetting: the ring says where the reader is and
    the walk keeps its own place, so the next press steps on rather than handing them
    back the ask they just put down.

    The landing is `body`, and a short page is where that stopped working. Chrome makes
    a scroll container focusable so the keyboard can scroll it, which is the whole of
    why `body.focus()` ever moved anything here — on a page that fits the window, the
    call did nothing and the reader stayed on the control the line had just promised to
    take them off."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    page.keyboard.press("n")
    expect(page.locator("#live-question[data-lf-ask]")).to_have_count(1)
    expect(page.locator(".lf-keyline")).to_contain_text("let go")
    # And the reference says the same press in its own words. It said "Back out one
    # layer" for every rung, which was true while every rung took a layer of chrome off
    # the page: standing on an ask is the reader holding something, with no layer over
    # the page at all, so the two surfaces named one press two ways.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text(
        "Let go of what you are standing on"
    )
    page.keyboard.press("Escape")  # the reference's own rung, which hands focus back
    expect(page.locator(".lf-help")).not_to_have_class(re.compile("open"))
    expect(page.locator("#live-question[data-lf-ask]")).to_have_count(1)

    page.keyboard.press("Escape")
    expect(page.locator("[data-lf-ask]")).to_have_count(0)
    assert page.evaluate("() => document.activeElement === document.body")
    expect(page.locator(".lf-keyline")).not_to_contain_text("let go")

    # The worklist keeps its place through that.
    page.keyboard.press("n")
    expect(page.locator("#sug-refill[data-lf-ask]")).to_have_count(1)

    # A window tall enough to hold the whole page, so body is no scroll container and
    # the browser will not focus it as a favour.
    resized(page, 1200, 1800)
    assert not page.evaluate(
        "() => document.body.scrollHeight > document.body.clientHeight"
    ), "the page still scrolls, so this proves nothing about a short one"
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "letting go left the reader holding the control on a page that fits the window"
    )
    assert errors == []
    page.close()


def test_travelling_to_an_element_lands_where_it_was_aimed(browser, serve):
    """Clicking a quoteless thread's § label brings its element to the middle — the
    promise made by callers that travel to a document anchor.

    It was 27px short of the middle in every one of them, and invisibly so: the
    scroller declares `scroll-padding-top` to keep a native fragment jump clear of
    the banner, and scrollIntoView's own "center" measures against the padded box
    rather than the viewport. So the arithmetic is the painted-range branch's, which
    never went through scrollIntoView and never drifted.

    A section taller than the viewport is the case centring cannot serve at all:
    put its middle in the middle and the heading the reader was sent to is above
    the top edge. It takes the banner clearance instead — read from the same
    declaration, so the number lives in one place — and the reader starts at the
    start."""
    url = serve(TRAVEL_PAGE)
    thread = {
        section: events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {section}.",
                "anchor": {"section": section},
            },
        )["id"]
        for section in ("flow", "long-part")
    }
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-comments").click()

    def quote(section):
        return page.locator(f'.lf-thread[data-id="{thread[section]}"] .lf-quote')

    # Centred: the destination the travel computed, which a glide toward it passes
    # through no earlier position that could be mistaken for.
    quote("flow").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('flow').getBoundingClientRect();
                   return r.height > 0
                       && Math.abs(r.top + r.height / 2 - innerHeight / 2) < 2; }"""
    )

    quote("long-part").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('long-part').getBoundingClientRect();
                   const clear = parseFloat(getComputedStyle(document.body).scrollPaddingTop);
                   return r.height > innerHeight && Math.abs(r.top - clear) < 2; }"""
    )
    assert errors == []
    page.close()


def test_an_ask_joins_the_walk_by_being_declared(browser, serve):
    """The list is never closed, and this is the test of it: a widget core has never
    heard of joins the count, the walk and the overlay by its registry entry alone,
    and the one that carried the whole feature leaves by losing its own.

    Driven by rewriting the page's vendored registry, because that is exactly what a
    project layer does — a page can add a widget to its own vocabulary, and nothing in
    the runtime, the banner or the key may need teaching about it."""
    url = serve(ASKS_PAGE)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    registry["lf-milestone"]["x-awaits"] = {"when": {"status": ["active", "blocked"]}}
    del registry["lf-suggestion"]["x-awaits"]
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))

    page, errors = open_page(browser, url)
    # Four, minus the suggestion that stopped declaring, plus the two milestones that
    # started — and no code anywhere knows any of those three tags.
    expect(page.locator(".lf-asks")).to_have_text("Asks (5)")
    # The blanket answer went with the declaration that named its verb.
    expect(page.locator(".lf-answer-all")).to_have_count(0)
    for expected in ["live-question", "t-baffles", "t-bath", "m-build", "m-install"]:
        page.keyboard.press("n")
        expect(page.locator(f"#{expected}")).to_have_attribute("data-lf-ask", "1")
    assert errors == []
    page.close()


def test_a_workers_report_paints_live_and_ends_at_the_version_that_answers_it(
    browser, serve
):
    """The agent channel, end to end in the browser: a `leaf report` reaches
    the open page on the next poll and paints as provisional news — the status
    attribute moves, the parent's done-fraction recounts, the element wears
    data-lf-reported rather than the user's pending mark, and a task reported
    into `review` joins the asks the banner counts. Then the version that
    answers the report by id takes the page back: replay skips a report the
    note named, so the overruling version's own state is what renders, with no
    provisional mark left on it. Last, the diff against the base version reads
    the base's state as the reader saw it — report included — so the overrule
    marks as a change even though the two files spell the same status."""
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    fraction = page.locator("#t-feeders > .lf-chips")
    expect(fraction).to_contain_text("1/2 done")
    expect(page.locator(".lf-asks")).to_be_hidden()  # nothing waits on the reader

    sent = CliRunner().invoke(
        cli_model.cli, ["report", str(d), "t-parser", "status", "status=review"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "review")
    expect(task).to_have_attribute("data-lf-reported", "1")
    expect(task).not_to_have_attribute("data-lf-pending", "1")
    # The marker is paint, so the word beside it (x-paints) has to move with the
    # attribute or a reader listening is told what the page said a poll ago.
    assert "review" in task.aria_snapshot()
    # A task at review is a standing ask however the status got there.
    expect(page.locator(".lf-asks")).to_have_text("Asks (1)")

    # A second report supersedes the first — absolute values fold — and the
    # fraction chip recounts across the tree.
    sent = CliRunner().invoke(
        cli_model.cli, ["report", str(d), "t-parser", "status", "status=done"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(task).to_have_attribute("status", "done")
    said = task.aria_snapshot()
    assert "done" in said and "review" not in said, said
    expect(fraction).to_contain_text("2/2 done")
    expect(page.locator(".lf-asks")).to_be_hidden()

    # The overruling version: its markup keeps `active` and publishes typed report
    # settlements resolved from `overruled`, so replay stops them
    # and the document speaks again.
    v2 = REPORT_PAGE.replace(
        '<lf-task id="t-parser" status="active">',
        '<lf-task id="t-parser" status="active" overruled>',
    )
    stamp_page(d, v2, "not done yet")
    assert len(events_model.read_events(d)[-1]["settles"]) == 2
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "active")
    expect(task).not_to_have_attribute("data-lf-reported", "1")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("1/2 done")

    # The diff's state half, mirror-image: v1's markup also said `active`, but
    # the reader last saw v1 wearing the report's `done`, so the overrule is a
    # change since the base — the report-layered base facet is what says so.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["t-parser"]
    assert errors == []
    page.close()


def test_a_rosters_row_says_when_the_log_last_heard_from_that_worker(browser, serve):
    """The half of a roster no version can write down. A standing report states what
    each worker is doing; only the log knows when it last said so, and a page that keeps
    a fleet is at its least trustworthy exactly when the reader has been away longest.
    So the row renders elapsed time from the newest report and re-renders on every poll.

    Then the case the line exists for: a claim of work nobody has refreshed. It is
    called out in words rather than in the tint alone, on the rope the banner already
    gives a page's one agent (quietSince), and only against a claim — an idle worker
    that has said nothing all day is idle, which is what it said."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    wren, finch = page.locator("#ag-wren"), page.locator("#ag-finch")
    # Before any worker has spoken, the row dates from the version that asserted it —
    # not from nothing, which would leave a fleet dead since last night reading exactly
    # like one published a minute ago.
    expect(wren.locator(".lf-heard")).to_contain_text("last heard")
    # The state is a word this module writes rather than paint the runtime speaks, so
    # a reader listening gets it from the row itself.
    assert "working" in wren.aria_snapshot()

    sent = CliRunner().invoke(
        cli_model.cli,
        # A state the markup does not already hold, or there is no news to paint: a
        # report saying what the page says is blessed silence, not provisional state.
        [
            "report",
            str(d),
            "ag-wren",
            "state",
            "state=waiting",
            "doing=rebasing onto main",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("rebasing onto main")
    expect(wren).not_to_have_attribute("doing", "rebasing onto main")
    expect(wren).to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-heard")).to_have_text("last heard just now")
    expect(wren.locator(".lf-cold")).to_have_count(0)

    stale_report(d, "ag-wren", "still rebasing", 3)
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("still rebasing")
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")

    # The same silence against no claim of work says nothing beyond its own age.
    stale_report(d, "ag-finch", "nothing", 3, state="idle")
    told(page)
    expect(finch.locator(".lf-doing")).to_have_text("nothing")
    expect(finch.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(finch.locator(".lf-cold")).to_have_count(0)

    # And it survives the version that answers the report, which is the case the whole
    # line exists for and the one an earlier build could never reach. Publishing absorbs
    # a report by id, so a roster reading standing reports blanked every row at every
    # publish — and the reader most needs this exactly where that left nothing: a worker
    # that claimed work, had the claim written into the document, and then died. The
    # provisional mark goes, because the document speaks again; the log's memory of who
    # last said anything does not, because no version can speak for that.
    stamp_page(d, ROSTER_PAGE, "absorbing")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)
    wren = page.locator("#ag-wren")
    expect(wren).not_to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-doing")).to_have_count(0)
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")
    assert errors == []
    page.close()


def test_claims_and_reports_share_one_canonical_update_feed(
    browser, serve, monkeypatch
):
    """Claims and reports keep distinct lifecycles behind one typed reading."""
    page, errors = open_page(browser, live_url(serve(ROSTER_PAGE)))
    d = serve.page_dir
    # Event ids and authored element ids belong to different identity spaces. Give
    # the thread and widget the same spelling so only the typed target can separate
    # their updates; a bare id or target lookup by store would merge them.
    thread = events_model.append_event(
        d,
        {
            "id": "ag-wren",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "ag-wren"},
            "text": "Can you check this worker's mount price?",
        },
    )
    told(page)

    report = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "ag-wren",
            "state",
            "state=working",
            "doing=checking the mount prices",
        ],
    )
    assert report.exit_code == 0, report.output
    report_event = events_model.read_events(d)[-1]
    claim_floor = report_event["seq"]
    # Force the same timestamp: causality, rather than wall-clock tie-breaking, must
    # order the two source records.
    with monkeypatch.context() as patch:
        patch.setattr(service_model, "now_iso", lambda: report_event["ts"])
        with service_model.PageTransaction(d) as transaction:
            transaction.set_status(
                "working",
                "checking the reader's question",
                work={
                    "subject": {"kind": "thread", "id": thread["id"]},
                    "after": claim_floor,
                },
            )
    told(page)

    updates = page.evaluate(
        "async () => (await import('/runtime/widget-api.js')).updateSequence()"
    )
    by_source = {update["source"]: update for update in updates}
    assert set(by_source) == {"claim", "report"}
    assert [update["source"] for update in updates] == ["report", "claim"]
    assert by_source["claim"]["ts"] == by_source["report"]["ts"]
    assert by_source["claim"] == {
        "id": by_source["claim"]["id"],
        "target": {"kind": "thread", "id": thread["id"]},
        "source": "claim",
        "action": "working",
        "detail": {"text": "checking the reader's question"},
        "text": "checking the reader's question",
        "ts": by_source["claim"]["ts"],
        "log_floor": claim_floor,
        "agent": "Claude",
        "session": by_source["claim"]["session"],
        "disposition": "effective",
    }
    assert by_source["report"] == {
        "id": by_source["report"]["id"],
        "target": {"kind": "widget", "id": "ag-wren"},
        "source": "report",
        "action": "state",
        "detail": {"state": "working", "doing": "checking the mount prices"},
        "text": "checking the mount prices",
        "ts": by_source["report"]["ts"],
        "revision": 1,
        "seq": by_source["report"]["seq"],
        "agent": "Claude",
        "session": by_source["report"]["session"],
        "disposition": "effective",
    }
    assert by_source["claim"]["session"]
    assert by_source["report"]["session"] == by_source["claim"]["session"]
    targeted = page.evaluate(
        """async () => {
            const feed = await import('/runtime/widget-api.js');
            return {
                widget: feed.updateSequence(document.querySelector('#ag-wren')),
                thread: feed.updateSequence({kind: 'thread', id: 'ag-wren'}),
                bare: (() => {
                    try { feed.updateSequence('ag-wren'); }
                    catch (error) { return `${error.name}: ${error.message}`; }
                })(),
            };
        }"""
    )
    assert [update["source"] for update in targeted["widget"]] == ["report"]
    assert [update["source"] for update in targeted["thread"]] == ["claim"]
    assert targeted["bare"].startswith("TypeError: update target must be")
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("checking the mount prices")

    # Each source ends at its own authority: a reply settles thread work, while a
    # version note settles the report.
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": thread["id"],
            "revision": 1,
            "text": "The mount price is in the attached quote.",
        },
    )
    stamp_page(d, ROSTER_PAGE, "recorded")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)

    updates = page.evaluate(
        "async () => (await import('/runtime/widget-api.js')).updateSequence()"
    )
    by_source = {update["source"]: update for update in updates}
    assert by_source["claim"]["disposition"] == "settled"
    assert by_source["report"]["disposition"] == "settled"
    expect(page.locator("#ag-wren .lf-doing")).to_have_count(0)
    assert errors == []
    page.close()


def test_report_words_wait_for_the_widget_state_deferred_by_a_drag(browser, serve):
    """A report's prose and durable fields describe the same committed reading."""
    page, errors = open_page(browser, serve(ROSTER_PAGE))
    d = serve.page_dir
    row = page.locator("#ag-wren")

    first = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "ag-wren",
            "state",
            "state=working",
            "doing=checking the first mount",
        ],
    )
    assert first.exit_code == 0, first.output
    told(page)
    expect(row).to_have_attribute("state", "working")
    expect(row.locator(".lf-doing")).to_have_text("checking the first mount")

    page.evaluate("document.body.classList.add('lf-dragging')")
    second = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "ag-wren",
            "state",
            "state=idle",
            "doing=checking the second mount",
        ],
    )
    assert second.exit_code == 0, second.output
    told(page)
    expect(row).to_have_attribute("state", "working")
    expect(row.locator(".lf-doing")).to_have_text("checking the first mount")

    page.evaluate("document.body.classList.remove('lf-dragging')")
    expect(row).to_have_attribute("state", "idle")
    expect(row.locator(".lf-doing")).to_have_text("checking the second mount")
    assert errors == []
    page.close()


def test_a_worker_that_has_never_reported_dates_from_its_version(browser, serve):
    """The direction a freshness line must never fail in. A row nobody has reported on
    is not of unknown age: its words were asserted when the version landed, and are
    exactly that old. Rendering nothing there was the first build's answer, and it hides
    the case the reader is most exposed to — a fleet published at six in the evening,
    every worker dead by seven, read at eight the next morning. Every row claims work,
    and with no report behind any of them there is no elapsed line to contradict it and
    no call-out: a dead fleet drawn exactly like a fresh one, one section under a banner
    whose whole design is that a claim nobody revises must not be repeated as fact."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    siskin = page.locator("#ag-siskin")
    expect(siskin.locator(".lf-heard")).to_have_text("last heard just now")
    expect(siskin.locator(".lf-cold")).to_have_count(0)

    backdate_note(d, 1, 3)
    told(page)
    expect(siskin.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(siskin.locator(".lf-cold")).to_have_text("quiet")
    # An idle worker is not called out for the same silence: it claimed nothing.
    expect(page.locator("#ag-finch .lf-heard")).to_have_text("last heard 3h ago")
    expect(page.locator("#ag-finch .lf-cold")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_rosters_clock_keeps_moving_when_the_server_stops_answering(browser, serve):
    """Elapsed time is rendered on the poll, and the poll is the one thing a dead server
    takes away. `poll()` returns early when the fetch brings nothing, so the sequence
    consumers heard no tick and every row froze the words it last drew — the banner
    saying the server is gone while the roster beside it went on reporting a four-minute
    silence for the rest of the afternoon. That is precisely the authored freshness this
    widget exists to replace, produced by the widget.

    The tick is what is asserted, and it is sampled from inside the page — the one
    licensed reason, that the fact is not one the browser reports from out here. Reading
    it through the words instead would mean waiting out a boundary `ago` crosses, whose
    only sub-minute one is a second wide; the words are then a pure function of this
    tick and a clock the platform owns."""
    url = serve(ROSTER_PAGE)
    page, errors = open_page(browser, url)
    page.evaluate(
        "() => { window.__ticks = 0;"
        " document.addEventListener('lf-actions', () => window.__ticks++); }"
    )
    page.route("**/api/state*", refuse)
    page.wait_for_function("() => window.__ticks >= 2")
    assert errors == []
    page.close()


def test_a_rosters_row_survives_the_polls_that_keep_it_fresh(browser, serve):
    """A row is a thing the reader is invited to select and point at, and it is also
    the one widget with a reason to touch itself every two seconds. Those pull against
    each other, and the first build lost: the clock re-rendered the whole row, so the
    words under a pointer were a different node on every poll — a selection collapsing
    mid-drag, focus dropped off the reference beside it, a click that straddles the
    swap landing on nothing. It is "Paint; don't wrap" reached by rebuilding instead of
    by wrapping, and it fails the same way: nothing errors, the page just stops taking
    the gesture.

    So the clock touches one text node and the structure is rebuilt only when a
    report moves that row. Asserted as node identity rather than as a selection, because
    identity is the property the rendering owes and a selection is one thing that rests
    on it."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    page.evaluate(
        "() => { window.__kept = [...document.querySelectorAll('#ag-wren .lf-doing,"
        " #ag-wren .lf-branch, #ag-wren .lf-state')].map(e => e.firstChild); }"
    )
    sent = CliRunner().invoke(
        cli_model.cli,
        ["report", str(d), "ag-finch", "state", "state=idle", "doing=picking up"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    ticked(page)
    # wren heard nothing in the read or the tick after it, so nothing of wren's may
    # have moved.
    assert page.evaluate(
        "() => window.__kept.every((n, i) => n === [...document.querySelectorAll("
        "'#ag-wren .lf-doing, #ag-wren .lf-branch, #ag-wren .lf-state')][i]?.firstChild)"
    )
    # And a report for this row does rebuild it, or the row would never move at all.
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "ag-wren",
            "state",
            "state=working",
            "doing=on to the baffles",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("on to the baffles")
    assert errors == []
    page.close()


def test_a_rosters_state_column_is_measured_from_the_words_it_holds(browser, serve):
    """The gutter every row hangs its state in is the widest of the five words, in the
    face this page is set in — the rule the pick column learned on a Linux runner,
    where DejaVu set "your pick" two pixels wider than the number a stylesheet had
    stated. So the column is asked of the rendered page here rather than pinned to a
    number: what a test can hold is that every row shares one column and that the
    column clears the widest word, which is what a stated number stopped doing
    silently."""
    url = serve(ROSTER_PAGE)
    page, errors = open_page(browser, url)
    pills = page.locator("#crew > lf-agent > .lf-state")
    expect(pills).to_have_count(3)
    lefts, widest = page.evaluate(
        "() => { const p = [...document.querySelectorAll('#crew > lf-agent > .lf-state')];"
        " return [p.map(e => Math.round(e.getBoundingClientRect().left)),"
        "         Math.max(...p.map(e => e.getBoundingClientRect().width))]; }"
    )
    assert len(set(lefts)) == 1, lefts
    room = page.evaluate(
        "() => parseFloat(getComputedStyle(document.getElementById('crew'))"
        ".getPropertyValue('--lf-state-room'))"
    )
    assert room >= widest, (room, widest)
    # And the row's own words start clear of it, or the column is decoration.
    assert page.evaluate(
        "() => { const g = document.querySelector('#ag-wren'), p = g.querySelector('.lf-state');"
        " return g.querySelector('strong').getBoundingClientRect().left"
        "      >= p.getBoundingClientRect().right; }"
    )
    assert errors == []
    page.close()


def test_a_recounted_fraction_holds_the_width_it_had(browser, serve):
    """A number the page rewrites unasked must not resize as it does.

    The done-fraction is the page's most-moved quantity: a worker reports a leaf
    and the parent recounts, on a poll, with nothing the reader did to account
    for the shift. It is apparatus, so it is set in the sans — and the sans gives
    each digit its own width where the serif carrying the prose gives them all
    one, which is why the figures are stated for the apparatus voice and not for
    the page. The chip is a filled pill, so its own box is what a reader watches
    twitch; where apparatus leads something else, that something moves with it —
    a metric's delta sits directly after the value it follows.

    Measured across the recount rather than a redraw, per tests/CLAUDE.md: the
    transition has to be one the figures actually decide. "1/2 done" to
    "2/2 done" stands 1.61px apart with proportional figures and identical with
    tabular, so deleting the declaration fails this. "0/3 done" to "3/3 done"
    would have been the vacuous choice — those two measure 0.03px apart either
    way, and the check would pass with the rule gone.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    # The fraction is the last chip its parent builds, after owner and when.
    fraction = page.locator("#t-feeders > .lf-chips span").last
    expect(fraction).to_have_text("1/2 done")
    before = fraction.bounding_box()["width"]

    sent = CliRunner().invoke(
        cli_model.cli, ["report", str(d), "t-parser", "status", "status=done"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    # The recount is the edge; the geometry is read once behind it.
    expect(fraction).to_have_text("2/2 done")
    after = fraction.bounding_box()["width"]

    assert abs(before - after) < 0.05, (
        f"the fraction resized as it recounted, {before}px to {after}px — a box "
        "the reader was given no gesture to explain"
    )
    assert errors == []
    page.close()


def test_the_render_gate_reports_a_server_that_stops_answering(
    browser, tmp_path, monkeypatch
):
    """A read that never comes back is a sentence, not a hang.

    Every document the gate reads used to be fetched inside the page, and
    `page.evaluate` sends the driver no timeout at all — measured, an evaluate
    awaiting a fetch that never answers is still running at 200s. So a server that
    accepted a request and then went quiet left `version check --render` running with
    nothing printed, which is the one failure a user cannot tell from slowness: the
    gate stopping is loud, and the gate never stopping looks like a slow machine.

    Stalled on the previous version's file, because the page never asks for that one
    itself — a path the runtime fetches on load would wedge the navigation instead,
    and the gate would report the banner it never saw rather than the read it never
    got. The deadline is shortened here for the same reason every wait in this suite
    states one: the number is not the subject, the bound is.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rendering_model, "SERVED_TIMEOUT_MS", 1500)
    d = tmp_path / "page"
    assert CliRunner().invoke(cli_model.cli, ["page", "init", str(d)]).exit_code == 0
    for n in (1, 2):
        (d / "versions" / f"v{n}.html").write_text(REPLY_HOST_PAGE)
        stamp_version_file(d, n, "t")

    asked = threading.Event()

    class Stalls(http_model.handler_for(d, TOKEN)):
        """Answers everything but the earlier version, which it accepts and drops."""

        def do_GET(self):
            if self.path.startswith("/versions/v1.html"):
                asked.set()
                time.sleep(300)  # longer than any patience the gate could have
                return
            super().do_GET()

    httpd = hosting_model.LeafHTTPServer(("127.0.0.1", 0), Stalls)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        failures = rendering_model.render_version(
            browser,
            f"http://127.0.0.1:{httpd.server_address[1]}/versions/v2.html?t={TOKEN}",
        )
    finally:
        httpd.shutdown()

    assert asked.is_set(), "nothing ever asked for the stalled file, so nothing stalled"
    assert failures and all("the server stopped answering" in f for f in failures), (
        f"a wedged server has to come back as a failure, and this came back as {failures}"
    )


def test_render_reports_markup_the_log_replays_over(browser, serve):
    """The static gate refuses a version that rewords what a decision rests on,
    but `chosen`, a card's column, and their kind say nothing a text diff can
    see — a version asserting them against the log used to lose silently, replay
    painting the user's state back over the author's intent. The render gate
    reports exactly that: an id the author changed since the previous version
    and replay then wrote. Silence (carrying the old markup forward) and honor
    (authoring the decided state) both stay clean, because silence changes no
    id and honor makes the replay a no-op."""
    url = serve(REPLAYED_PAGE)
    d = serve.page_dir
    for widget, action, detail in [
        ("approach", "choose", {"options": ["opt-shim"]}),
        ("work", "move", {"card": "card-importer", "to": "col-done", "index": 0}),
    ]:
        events_model.append_event(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )

    def stamp(n, html):
        (d / "versions" / f"v{n}.html").write_text(html)
        stamp_version_file(d, n, "t")
        return url.replace("v1.html", f"v{n}.html")

    # v2 says nothing about either decision; both stand, and nothing is reported.
    assert rendering_model.render_version(browser, stamp(2, REPLAYED_PAGE)) == []

    # v3 honors both: the pick authored, the card in its dragged-to column.
    honored = REPLAYED_PAGE.replace('id="opt-shim"', 'id="opt-shim" chosen')
    honored = honored.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    assert rendering_model.render_version(browser, stamp(3, honored)) == []

    # v4 asserts the other option and re-authors the card into Doing: both
    # widgets changed since v3 and replay overrides both — the author must hear.
    contradicted = REPLAYED_PAGE.replace('id="opt-stage"', 'id="opt-stage" chosen')
    with rendering_model.preview_source_server(
        d, contradicted.encode(), 4
    ) as preview_url:
        failures = rendering_model.render_version(browser, preview_url)
    assert len(failures) == 2, failures
    assert any("id=approach" in f and "opt-stage" in f for f in failures), failures
    assert any("id=work" in f and "card-importer" in f for f in failures), failures


def test_the_render_gate_applies_every_standing_action_a_second_time(browser, serve):
    """Absoluteness is what makes a fold a fold, and it is the one thing about a widget
    module no reading of a rendered page can see: a relative implementation renders
    perfectly and costs the user their gesture later, on the poll that replays it. So
    the gate applies each standing action again and asks what moved, and the shipped
    vocabulary has nothing to do — a card placed where it already is, a pick set to
    what it already holds, a body assigned the words it already reads.

    The corpus cannot say this on its own: `test_example_renders` serves every example
    under a log holding one note, so the fold is empty there and the reading passes
    without applying anything. This page is the log the examples haven't got, and the
    floor is that the standing state covers every verb the registry declares — a verb
    added without an event here fails rather than going unexercised."""
    url = serve(STANDING_PAGE)
    for widget, action, detail in STANDING_ACTIONS:
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
    # The agent channel through its own door, which is the only way a report is
    # written: both channels replay, so both rest on the same contract. A roster row
    # carries recorded state and a generated clause under one verb, so re-applying has
    # to leave both where they stand. Splitting the clause into another verb would make
    # the two reports compete for one fold key.
    for widget, verb, fields in [
        ("ab-baffles", "status", ["status=done"]),
        ("ab-wren", "state", ["state=blocked", "doing=waiting on the fixture"]),
    ]:
        sent = CliRunner().invoke(
            cli_model.cli, ["report", str(serve.page_dir), widget, verb, *fields]
        )
        assert sent.exit_code == 0, sent.output

    page, errors = open_page(browser, url)
    standing = page.evaluate("""async () => (await import('/runtime/widget-api.js')).standingState()
        .map(({ widget, facet, action }) => [widget.id, widget.localName, facet, action])""")
    page.close()
    registry = validation_model.incoming_registry(
        [
            schema_model.ASSETS,
            schema_model.DEFAULT_PACKAGE,
            COMMAND_HUB_PACKAGE,
        ]
    )
    declared = {
        (tag, verb)
        for tag, entry in registry.items()
        if tag.startswith("lf-")
        for channel in ("x-state", "x-report")
        for verb in entry.get(channel, {})
    }
    assert {(tag, verb) for _id, tag, _facet, verb in standing} == declared, (
        "the gate applies the standing state, so a declared verb missing from it is a "
        f"verb nothing here re-applies: page holds {standing}, registry declares "
        f"{sorted(declared)}"
    )
    assert {
        (facet, action)
        for widget, _tag, facet, action in standing
        if widget == "ab-pick"
    } == {("selection", "choose"), ("completion", "answer")}
    assert errors == []
    assert rendering_model.render_version(browser, url) == []


def test_a_reader_action_outranks_later_news_on_the_same_coordinate(
    browser, serve, tmp_path, monkeypatch
):
    """The projection, not channel replay order, is the DOM's authority. A worker's
    later count remains report history, but it cannot paint over the reader's action
    on the same unit and facet; both log records are ready once that one coordinate is
    committed."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-tally"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    entries["lf-tally"].setdefault("required", []).append("count")
    entries["lf-tally"]["x-example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    entries["lf-tally"]["properties"]["restated"] = {"type": "boolean"}
    entries["lf-tally"]["properties"]["overruled"] = {"type": "boolean"}
    record = {"kind": "value", "attr": "count", "value": "count"}
    count_detail = {
        "type": "object",
        "properties": {"count": {"type": "string", "pattern": "^[0-9]+$"}},
        "required": ["count"],
        "additionalProperties": False,
    }
    entries["lf-tally"]["x-state"] = {
        "set": {
            "detail": count_detail,
            "facet": "count",
            "unit": "widget",
            "record": record,
        }
    }
    entries["lf-tally"]["x-report"] = {
        "measure": {
            "detail": count_detail,
            "facet": "count",
            "unit": "widget",
            "record": record,
        }
    }
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(
        """\
import { once } from "/runtime/widget-api.js";
customElements.define("lf-tally", class extends HTMLElement {
  connectedCallback() { once(this); }
  applyAction(_action, detail) {
    this.setAttribute("count", detail.count);
  }
});
"""
    )
    url = serve(RELATIVE_WIDGET_PAGE)
    for kind, author, widget, action, count in [
        ("action", "user", "tally-fitted", "set", "7"),
        ("report", "claude", "tally-fitted", "measure", "9"),
        ("action", "user", "tally-seen", "set", "5"),
    ]:
        events_model.append_event(
            serve.page_dir,
            {
                "kind": kind,
                "author": author,
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": {"count": count},
            },
        )

    page, errors = open_page(browser, url)
    expect(page.locator("#tally-fitted")).to_have_attribute("count", "7")
    expect(page.locator("#tally-seen")).to_have_attribute("count", "5")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")
    standing = page.evaluate(
        """async () => (await import('/runtime/widget-api.js')).standingState()
          .filter(state => state.widget?.id === 'tally-fitted')
          .map(state => [state.action, state.detail.count])"""
    )
    assert standing == [["set", "7"]]

    page.keyboard.press("z")
    round_trip(page)
    expect(page.locator("#tally-seen")).to_have_attribute("count", "0")
    assert errors == []
    page.close()


def test_a_part_and_its_own_widget_keep_same_named_facets_independent(
    browser, serve, tmp_path, monkeypatch
):
    """Facet names are local to their owning widget contract. A container's
    placement of part `piece` and that element's own `placement` facet therefore
    coexist even though unit and facet text are identical; both owners reconcile."""
    monkeypatch.chdir(tmp_path)
    for tag, upgrade in (
        ("lf-owner", True),
        ("lf-zone", False),
        ("lf-piece", True),
    ):
        author_test_widget(tmp_path, tag, upgrade=upgrade)

    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    owner = entries["lf-owner"]
    owner["x-content"] = "items"
    owner["x-state"] = {
        "move": {
            "detail": {
                "type": "object",
                "properties": {
                    "piece": {"type": "string"},
                    "to": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                },
                "required": ["piece", "to", "index"],
                "additionalProperties": False,
            },
            "facet": "placement",
            "unit": "piece",
            "record": {
                "kind": "position",
                "within": "lf-zone",
                "value": "to",
                "order": "index",
            },
        }
    }
    owner["x-example"] = (
        '<lf-owner id="sample-owner"><lf-zone id="sample-zone">'
        '<lf-piece id="sample-piece" pinned="no">Piece</lf-piece>'
        "</lf-zone></lf-owner>"
    )
    zone = entries["lf-zone"]
    zone["x-parent"] = ["lf-owner"]
    zone["x-content"] = "items"
    zone.pop("x-example", None)
    piece = entries["lf-piece"]
    piece["x-parent"] = ["lf-zone"]
    piece["properties"] |= {
        "pinned": {"type": "string"},
        "restated": {"type": "boolean"},
    }
    piece.setdefault("required", []).append("pinned")
    piece["x-state"] = {
        "pin": {
            "detail": {
                "type": "object",
                "properties": {"pinned": {"type": "string"}},
                "required": ["pinned"],
                "additionalProperties": False,
            },
            "facet": "placement",
            "unit": "widget",
            "record": {"kind": "value", "attr": "pinned", "value": "pinned"},
        }
    }
    piece.pop("x-example", None)
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-owner.js").write_text(
        """\
import { once } from "/runtime/widget-api.js";
customElements.define("lf-owner", class extends HTMLElement {
  connectedCallback() { once(this); }
  applyAction(_action, detail) {
    const piece = document.getElementById(detail.piece);
    const zone = document.getElementById(detail.to);
    zone.insertBefore(piece, [...zone.children][detail.index] ?? null);
  }
});
"""
    )
    (tmp_path / ".leaf" / "widgets" / "lf-piece.js").write_text(
        """\
import { once } from "/runtime/widget-api.js";
customElements.define("lf-piece", class extends HTMLElement {
  connectedCallback() { once(this); }
  applyAction(_action, detail) { this.setAttribute("pinned", detail.pinned); }
});
"""
    )
    html = leaf_page(
        "owned coordinates",
        """<h1>Owned coordinates</h1><lf-owner id="owner">
<lf-zone id="zone-a"><lf-piece id="piece" pinned="no">Piece</lf-piece></lf-zone>
<lf-zone id="zone-b"></lf-zone></lf-owner>""",
    )
    url = serve(html)
    for event in (
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "owner",
            "action": "move",
            "detail": {"piece": "piece", "to": "zone-b", "index": 0},
        },
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "piece",
            "action": "pin",
            "detail": {"pinned": "yes"},
        },
    ):
        events_model.append_event(serve.page_dir, event)

    page, errors = open_page(browser, url)
    expect(page.locator("#zone-b > #piece")).to_have_count(1)
    expect(page.locator("#piece")).to_have_attribute("pinned", "yes")
    standing = page.evaluate(
        """async () => (await import('/runtime/widget-api.js')).standingState()
          .filter(state => state.unit === 'piece' && state.facet === 'placement')
          .map(state => [state.widget.id, state.action])"""
    )
    assert standing == [["owner", "move"], ["piece", "pin"]]
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")
    assert errors == []
    page.close()


def test_the_render_gate_catches_a_relative_apply_action(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the module contract's first state rule, and for
    both readings the gate takes of it. One project widget steps its count from the
    count it reads and appends its caption to the caption it reads: right once, and
    wrong every time after, because the page has already replayed the actions and the
    poll replays the user's own gestures back at them. The finding names the widget,
    both verbs, and what moved.

    Two facets on one unit prove both can stand while exercising the two readings that
    catch different things. The count is markup, so `shallowSigs` sees it; the caption
    is text, which that signature excludes on purpose, so only the facet's declared
    record form reaches it — a limb of the gate that would otherwise never have fired."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-tally"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    entries["lf-tally"].setdefault("required", []).append("count")
    entries["lf-tally"]["x-content"] = "data"
    entries["lf-tally"]["x-example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    # The registry holds a widget-unit verb to the attribute a version retracts a
    # decision with, so a state channel arrives with its way out of one.
    entries["lf-tally"]["properties"]["restated"] = {"type": "boolean"}
    entries["lf-tally"]["x-state"] = {
        "step": {
            "detail": {
                "type": "object",
                "properties": {"count": {"type": "string", "pattern": "^[0-9]+$"}},
                "required": ["count"],
                "additionalProperties": False,
            },
            "facet": "count",
            "unit": "widget",
            "record": {"kind": "value", "attr": "count", "value": "count"},
        },
        "caption": {
            "detail": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            "facet": "caption",
            "unit": "widget",
            "record": {"kind": "body", "value": "text"},
        },
    }
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(RELATIVE_WIDGET_MODULE)
    url = serve(RELATIVE_WIDGET_PAGE)
    for widget, action, detail in [
        ("tally-fitted", "step", {"count": "3"}),
        ("tally-fitted", "caption", {"text": "Two greys at the north feeder."}),
    ]:
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )

    failures = rendering_model.render_version(browser, url)

    tail = (
        ". Replay lays every standing action over the state they already "
        "produced, so state the whole value from the detail rather than stepping "
        "from what the page shows"
    )
    assert [f for f in failures if "is relative" in f] == [
        "[light] <lf-tally id=tally-fitted> applyAction(step, caption) is relative — "
        "re-applying the standing log moved tally-fitted, the caption state recorded "
        "on tally-fitted" + tail,
    ], failures


def test_a_widget_standing_out_of_place_is_a_page_the_gate_reports(
    browser, serve, tmp_path, monkeypatch
):
    """The premise the test below rests on, stated where it can fail on its own.

    With nothing in the log to settle it, <lf-drift> keeps the offset its markup
    states for as long as the page is open, and its words sit over the paragraphs
    under it. That is a page the covered-words reading reports — so the test below,
    which serves this same markup and expects nothing, is measuring the gate's
    patience rather than a page that was never broken."""
    url = serve(drifting_widget(tmp_path, monkeypatch))

    covered = [
        f for f in rendering_model.render_version(browser, url) if "same place" in f
    ]

    assert covered and all("drift-note" in f for f in covered), covered


def test_a_page_at_rest_is_read_across_a_widgets_own_root(
    browser, serve, tmp_path, monkeypatch
):
    """Whether the page is still moving is asked of every tree the page is in.

    A document answers for its own tree alone: `document.getAnimations()` returns
    nothing for an element inside a widget's shadow root, and `{subtree: true}` on
    the root element returns nothing either. A widget drawing itself into place in
    there grows the host box the gate's own readings measure, so a reading that
    asked the document would call that page still and read it mid-move — the fault
    the wait exists to prevent, surviving inside the one place a widget is most
    likely to draw."""
    url = serve(drifting_widget(tmp_path, monkeypatch, deep=True))
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    # The banner's dot pulses forever and is deliberately not the page moving, so the
    # control asks after a finite end rather than after an empty list.
    assert (
        page.evaluate(
            "() => document.getAnimations().filter(a => Number.isFinite("
            "  a.effect?.getComputedTiming().endTime)).length"
        )
        == 0
    ), "the document tree already answers for this one, so the reading proves nothing"
    assert render_checks_model.evaluate_probe(page, "moving") == [
        "<lf-drift id=drift-note>"
    ]
    assert errors == []
    page.close()


def test_a_module_that_stages_bare_text_is_refused_in_its_own_name(
    browser, serve, tmp_path, monkeypatch
):
    """The one text these walks reach with no element over it, and the page says whose.

    A widget may render the page's words into its own shadow root, and the passage walk
    crosses in after them. What it cannot take is a text node put straight on the root:
    `parentElement` is null there, so those words have no block to sit in, no cell to be
    fenced by and nothing for a mark to hang on, and admitting them would split the
    page's reading from the file's. The page refuses to present at all, which is the
    loud direction — but the refusal used to arrive as `Cannot read properties of null
    (reading 'closest')` over a blank page, naming neither the widget nor the mistake,
    which is a bug report against leaf rather than against the module that caused it."""
    url = serve(drifting_widget(tmp_path, monkeypatch, bare=True))
    page = browser.new_page(
        viewport=render_checks_model.RENDER_VIEWPORT, color_scheme="light"
    )
    # The first thing the page says in anger, whatever that turns out to be: waiting
    # for the wording under test would make a page that says something else read as a
    # page that says nothing, and the message is the whole subject here.
    with page.expect_console_message(lambda message: message.type == "error") as caught:
        page.goto(url, wait_until="commit")
    refusal = caught.value.text

    assert '<lf-drift id="drift-note">' in refusal, refusal
    assert "They came over the fence" in refusal, refusal
    assert "closest" not in refusal, (
        "the refusal is still a property name, which reads as leaf being broken: "
        + refusal
    )
    assert page.evaluate("() => document.body.dataset.lfUpgraded") is None, (
        "the page presented anyway, so the words with nothing over them are in it"
    )
    page.close()


def test_the_render_gate_reads_a_page_that_has_finished_arriving(
    browser, serve, tmp_path, monkeypatch
):
    """A page finishes twice, and the second ending arrives moving.

    `lf-upgraded` is the first: every widget upgraded, the geometry final. The
    runtime writes it in the same breath as it *starts* the first read and never
    awaits that read, so a gate reading there reads the authored page — here, a
    widget standing 120px out of place with its words over the paragraphs below it.
    `lf-applied` is the second, and the frame it lands in is the first frame of the
    move it describes: a read that brings nothing presents the authored page
    deliberately, so the replay after it crosses the presentation boundary and moves
    rather than teleports.

    Both windows are load-shaped — a busy server, a few hundred milliseconds — which
    is how this page passed at a desk and reported words drawn over words under a
    full suite. Holding the action back until the page's first read has answered, and
    the gate's own read until the action is in, makes the window the same every run:
    the page reads as broken for about three seconds, and the gate must have nothing
    to say about it. Either wait on its own leaves this failing."""
    # For the page directory and its vendored layer; this test serves it itself.
    serve(drifting_widget(tmp_path, monkeypatch))
    landed = []
    # The action is in the log and the gate may read it. Both halves of the window are
    # this one fact, so the hold below and the append are the same statement made twice.
    arrived = threading.Event()
    expired = []
    settle = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "drift-note",
        "action": "settle",
        "detail": {"offset": "0"},
    }

    class TheLogArrivesLate(http_model.handler_for(serve.page_dir, TOKEN)):
        """The action reaches the log between the page's first read and the gate's.

        A page whose first read brings nothing is presented on the authored markup
        deliberately, so the replay that follows is past the presentation boundary
        and moves rather than teleports. The page's read is told from the gate's own
        reading of the same document by the Referer a page fetch carries and an
        APIRequestContext does not: the action goes in behind the page's read, and
        the gate's is held until it has, so the gate always sees a log with the action
        in it and always has a caught-up stamp to wait for.

        Holding it is the whole arrangement rather than a margin. The page stamps
        itself upgraded without awaiting its first read, so the gate is free to reach
        `/api/state` while that read is still in flight — and under a busy server it
        does, whereupon it counts an empty log, waits for nothing, and reads the page
        mid-move. That is this test's own failure and not the gate's."""

        def do_GET(self):
            state_read = self.path.startswith("/api/state")
            page_read = state_read and self.headers.get("Referer")
            # Bounded, and far inside the gate's own deadline for a served document: a
            # runtime that stopped reading state at startup is named by the assertion
            # below rather than by a gate whose server appeared to stop answering.
            if state_read and not page_read and not arrived.wait(10):
                expired.append(self.path)
            super().do_GET()
            if page_read and not landed:
                landed.append(self.headers["Referer"])
                events_model.append_event(serve.page_dir, settle)
                arrived.set()

    httpd = hosting_model.LeafHTTPServer(("127.0.0.1", 0), TheLogArrivesLate)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        late = f"http://127.0.0.1:{httpd.server_address[1]}/versions/v1.html?t={TOKEN}"
        failures = rendering_model.render_version(browser, late)
    finally:
        httpd.shutdown()
    # The window first, because the gate's verdict on a window that never opened says
    # nothing: an empty log is a page with nothing to replay and nothing to report.
    assert landed and "/versions/v1.html" in landed[0], (
        "the action never went in behind the page's first read, so the window this "
        f"rests on never opened: {landed}"
    )
    assert not expired, (
        "the gate's read was released by the 10s bound rather than by the append, so "
        f"it read a log with nothing in it to wait for: {expired}"
    )
    assert failures == []


def test_replay_signatures_distinguish_widget_state_from_runtime_paint(browser, serve):
    """A widget may use the runtime's namespace for state without making that state
    runtime paint. Replaying a suggestion changes only data-lf-state on its authored
    element, so the replay record must name it; data-lf-pending on the same element is
    the runtime's own annotation and must not change the signature."""
    url = serve(SUGGESTION_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    page.wait_for_function(
        "() => (document.body.dataset.lfReplayWrote ?? '').split(' ').includes('sug-refill')"
    )

    signatures = page.evaluate("""async () => {
        const { shallowSigs } = await import("/runtime/widget-api.js");
        const widget = document.getElementById("sug-refill");
        const read = () => shallowSigs(document.body).get(widget.id);
        const decided = read();
        widget.setAttribute("data-lf-pending", "probe");
        const painted = read();
        widget.removeAttribute("data-lf-state");
        const undecided = read();
        return { decided, painted, undecided };
    }""")
    assert signatures["decided"] == signatures["painted"], (
        "runtime-owned pending paint became authored state in the replay signature"
    )
    assert signatures["decided"] != signatures["undecided"], (
        "widget-owned data-lf-state disappeared with the runtime's private attributes"
    )
    assert errors == []
    page.close()


def test_a_moved_card_wears_its_pending_state_until_honored(browser, serve):
    """A move outlives its toast: the card the user moved stays visibly
    marked as recorded-but-unwritten and its grip says so, in the tab that moved
    it and in a fresh replay alike, because the runtime compares the page's state
    against the version's own snapshot rather than remembering who wrote what.
    The card the move displaced stays unmarked — the log named one card, not its
    neighbours. The honoring version says the state itself, so on it the
    disagreement and both renderings are gone."""
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)

    # The keyboard gesture takes the same #send path as a drag. The sender's own
    # replay is a no-op, which is exactly the case the version snapshot covers.
    page.get_by_role("button", name="Move: Wire the importer — Doing").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator("#card-importer")).to_have_attribute("data-lf-pending", "1")
    expect(page.locator("#card-notes")).not_to_have_attribute("data-lf-pending", "1")
    expect(
        page.get_by_role(
            "button",
            name="Move: Wire the importer — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()

    # A fresh tab reads the same fact from replay alone, and paints both its
    # visible outline and its durable spoken state.
    second, second_errors = open_page(browser, url)
    expect(second.locator("#card-importer")).to_have_attribute("data-lf-pending", "1")
    expect(
        second.get_by_role(
            "button",
            name="Move: Wire the importer — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()
    assert (
        second.locator("#card-importer").evaluate(
            "el => getComputedStyle(el).outlineStyle"
        )
        == "solid"
    )

    # The honoring version authors the card where the user put it; replay
    # no-ops against it and the mark has nothing left to say.
    d = serve.page_dir
    honored = REPLAYED_PAGE.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    (d / "versions" / "v2.html").write_text(honored)
    stamp_version_file(d, 2, "t")
    third, third_errors = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(third.locator("#col-done #card-importer")).to_be_visible()
    # Absence only counts once replay has decided every action.
    third.wait_for_function("() => document.body.dataset.lfApplied === '1'")
    expect(third.locator("#card-importer")).not_to_have_attribute(
        "data-lf-pending", "1"
    )
    expect(
        third.get_by_role("button", name="Move: Wire the importer — Done", exact=True)
    ).to_be_visible()

    assert errors == [] and second_errors == [] and third_errors == []
    for tab in (page, second, third):
        tab.close()


def test_a_pending_suggestion_can_be_discussed_instead_of_decided(browser, serve):
    """✓ and ✗ are the visible affordances, but a proposal a user half-agrees
    with wants a sentence, not a verdict: the proposed words are ordinary page
    text, so selecting them and commenting works like anywhere else. Then the
    decision they eventually take has to reach the thread — rejecting retires the
    text the comment was made on, and a comment pointing into markup nobody can
    see has to read as detached rather than as a live mark that jumps nowhere."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#sug-refill lf-new'));
        getSelection().removeAllRanges();
        getSelection().addRange(r);
        document.body.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }""")
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    page.wait_for_selector(".lf-composer", state="visible")
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "Refill a feeder when its camera shows it half-empty."
    page.locator(".lf-composer textarea").fill("Half-empty by whose reading?")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()

    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).to_be_visible()
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert (
        painted(page, "lf-mark")
        == "Refill a feeder when its camera shows it half-empty."
    )

    page.locator("[data-lf-for='sug-refill'] .lf-sug-reject").click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "", (
        "a mark stayed painted on text the user's own decision removed"
    )
    assert errors == []
    page.close()


def test_a_decision_already_in_the_log_retires_its_slot_at_load(browser, serve):
    """The test above takes the decision in front of the user, on a page that has
    been up long enough for everything to have arrived. Here the log holds it before
    the page opens, which is what puts the anchor pass's skip list on the clock: the
    registry names the slot a decision retires (x-retired-when), and the registry
    arrives over the network, after the module that reads it has evaluated. Replay
    settles the suggestion on the first poll, so the pass that runs with it has to be
    skipping lf-old already — or the page opens with a live mark on words the user
    accepted away."""
    url = serve(
        SUGGESTION_PAGE, anchored=[("replace", "Refill every feeder each morning.")]
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the first pass anchored inside a slot the user's decision had retired"
    )
    assert errors == []
    page.close()


def test_a_slot_naming_two_holders_retires_under_neither_until_decided(
    browser, serve, tmp_path, monkeypatch
):
    """`x-parent` is a list, and the retired-slot selector is built from it. Written
    `${entry["x-parent"]}` the list interpolates comma-joined, so a slot naming two
    holders wrote a selector *list* whose first member was the bare holder tag: every
    instance of it read as a retired slot however the log stood, its words silenced
    from the anchor pass, while the pair that was meant matched nothing at all.

    Unreachable until this layer's licensing opened `x-retired-when` past the
    suggestion family, which is why the shipped vocabulary — every slot of it naming
    one holder — could never have said so. The page holds an undecided trial, so
    nothing here is retired and a quote inside it must anchor like any other."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(TWO_HOLDER_PAGE, anchored=[("th-now", "warmed on every deploy")])
    page, errors = open_page(browser, url)
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(page.locator(".lf-thread .lf-quote").first).not_to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") != "", (
        "the quote found nothing to paint: an undecided holder read as a retired slot, "
        "so the anchor pass skipped every word inside it"
    )
    assert errors == []
    page.close()


def test_a_settled_third_party_holder_wears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch
):
    """A settlement is the layer's rendering of the log's decision, never a module
    obligation: the trial's module only defines the element and
    supplies no applyAction at all — and once its decision replays the holder wears
    data-lf-state, the retired slot is marked and hidden by the theme's one generic
    rule, and the quote anchored in it detaches instead of pointing at words the
    page's reading has dropped. The mark and the hide used to be each holder
    module's own duty, stated in the module contract and the key table and enforced
    nowhere, and the first family that forgot would have split the page's reading
    from the file's in silence. The second half drives it all back out: the fold
    keeps the last surviving action per facet and unit, so a widget-unit verb on
    the settlement facet that settles nothing displaces the decision, and the mark,
    the marker and the hide follow it."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(TWO_HOLDER_PAGE, anchored=[("th-next", "warmed on the first request")])
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "shelve",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the quote matched inside a slot the logged decision retired: nothing wrote "
        "the settlement mark for a module that doesn't"
    )
    assert errors == []
    page.close()

    # The mark follows the fold out as well as in: the file's standing state is the
    # last surviving action per facet and unit, so a widget-unit verb on the same
    # facet that settles nothing displaces the decision, and a mark left standing
    # would silence a slot the log has handed back.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "pause",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    assert page.locator("#th-cache").get_attribute("data-lf-state") is None
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(page.locator(".lf-thread .lf-quote").first).not_to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") != "", (
        "the displaced decision's slot is back on the page, so its quote must "
        "anchor again"
    )
    assert errors == []
    page.close()


def test_withdrawing_a_recorded_settlement_clears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch
):
    """Authored reconstruction states markup, not a logged decision. A holder may
    validly record the value carried by its settlement facet; restoring that value
    after undo must not re-mark the withdrawn action or keep its slot retired."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    holder = entries["lf-trial"]
    holder["properties"]["decision"] = {"enum": ["open", "shelved"]}
    holder.setdefault("required", []).append("decision")
    holder["x-example"] = holder["x-example"].replace(
        'id="x-trial"', 'id="x-trial" decision="open"'
    )
    detail = {
        "type": "object",
        "properties": {"decision": {"enum": ["open", "shelved"]}},
        "required": ["decision"],
        "additionalProperties": False,
    }
    record = {"kind": "value", "attr": "decision", "value": "decision"}
    for spec in holder["x-state"].values():
        spec["detail"] = detail
        spec["record"] = record
    registry_path.write_text(json.dumps(entries))
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """import { once } from "/runtime/widget-api.js";
customElements.define("lf-trial", class extends HTMLElement {
  connectedCallback() { once(this); }
  applyAction(_action, detail) { this.setAttribute("decision", detail.decision); }
});
"""
    )
    page_html = TWO_HOLDER_PAGE.replace(
        '<lf-trial id="th-cache">', '<lf-trial id="th-cache" decision="open">'
    )
    url = serve(page_html)
    decision = events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "shelve",
            "detail": {"decision": "shelved"},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("decision", "shelved")
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()

    events_model.append_event(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": decision["id"]},
    )
    told(page)
    expect(page.locator("#th-cache")).to_have_attribute("decision", "open")
    expect(page.locator("#th-cache")).not_to_have_attribute(
        "data-lf-state", re.compile(r".+")
    )
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    assert errors == []
    page.close()


def test_a_throwing_settlement_still_reaches_the_layers_terminal_state(
    browser, serve, tmp_path, monkeypatch
):
    """A module failure is terminal rather than an endless replay retry, and the
    layer's generic settlement contract still applies: readiness, the holder mark,
    and the visible fail-soft box must agree on that one consumed action."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """\
customElements.define("lf-trial", class extends HTMLElement {
  applyAction() { throw new Error("trial replay broke"); }
});
"""
    )
    url = serve(TWO_HOLDER_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "shelve",
            "detail": {},
        },
    )

    page, errors = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache .lf-error")).to_contain_text("trial replay broke")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")
    assert any(
        "<lf-trial> applyAction(shelve) threw: trial replay broke" in error
        for error in errors
    ), errors
    page.close()


def test_the_render_gate_holds_a_settled_slot_to_the_logs_decision(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the settlement reading, in both directions. The bare family first
    proves the gate accepts a holder that brings nothing of its own — the layer's
    default hide is the whole of its disappearance. Then the one generic hide rule is
    stripped from the vendored theme, standing in for whatever re-shows a retired
    slot (a later layer's rule outranking the default, a module re-showing what it
    folded): the words stay on screen where the reader can select what no comment
    can anchor to, and the gate must say so. Then the theme goes back and the
    vendored module is rewritten to mark every trial at upgrade: on the undecided
    spare that is a settlement the log never decided, silencing words the reader can
    still see, and the gate must say that too. Both failures render perfectly, which
    is why each is put back deliberately."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(TWO_HOLDER_SPARE_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "shelve",
            "detail": {},
        },
    )
    assert rendering_model.render_version(browser, url) == []

    hide = "[data-lf-retired] { display: none; }"
    vendored = serve.page_dir / "theme.css"
    css = vendored.read_text()
    assert css.count(hide) == 1
    vendored.write_text(css.replace(hide, ""))
    failures = rendering_model.render_version(browser, url)
    assert any(
        "<lf-trial id='th-cache'> settled `shelve` and its <lf-proposed> still shows"
        in failure
        for failure in failures
    ), failures

    vendored.write_text(css)
    module = serve.page_dir / "widgets" / "lf-trial.js"
    source = module.read_text()
    upgrade_line = "if (!once(this)) return;"
    assert source.count(upgrade_line) == 1
    module.write_text(
        source.replace(
            upgrade_line,
            upgrade_line + '\n      this.setAttribute("data-lf-state", "shelve");',
        )
    )
    failures = rendering_model.render_version(browser, url)
    assert any(
        "<lf-trial id='th-spare'> wears data-lf-state=\"shelve\" where the log "
        "records no decision" in failure
        for failure in failures
    ), failures


def test_a_label_in_a_retired_slot_leaves_the_page_with_the_slot(browser, serve):
    """A decided suggestion's losing slot is off the page, and a label inside it goes
    too. The label is the one thing that reads back over chrome — a pick mark says
    "chosen" and declares those words the page's, which is what lets a user point at
    it anywhere else — so the rule has to stop at the slot: a marker that outranks a look
    must not outrank a decision, or a quote lands in the half the user removed."""
    url = serve(RETIRED_WIDGET_PAGE, anchored=[("sug-swap", "chosen")])
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-swap",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-swap lf-old")).to_be_hidden()
    assert (
        page.locator("#old-lax .lf-pick").evaluate("el => el.textContent") == "chosen"
    ), "fixture is not exercising the case — the mark the slot hides never rendered"
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "a quote matched inside the half the user accepted away, because the "
        "label there declared itself the page speaking"
    )
    assert errors == []
    page.close()


def test_a_decision_that_empties_its_widget_detaches_the_element_anchor(browser, serve):
    """An element anchor asks whether its section is still on the user's page,
    and for a suggestion that settles to nothing — an insertion refused — the
    markup's presence is the wrong answer: the thread read as attached while its
    outline drew nothing. Pending, the wrapper is a thing to point at; refused, the
    thread detaches like any passage the decision removed."""
    url = serve(SUGGESTION_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is thistle worth a feeder?",
            "anchor": {"section": "sug-thistle"},
        },
    )
    page, errors = open_page(browser, url)
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    # Pending, the outline hangs on a box the reader can see, and it is read as a box
    # rather than as a class: the class sat on the wrapper while the wrapper was
    # display: contents and painted no outline, so the half of this docstring about
    # drawing nothing was true of the attached case too. The wrapper draws its own box
    # now, so the mark is the wrapper itself rather than the slot it showed through.
    shown = page.locator("#sug-thistle.lf-mark-el")
    expect(shown).to_have_count(1)
    box = shown.evaluate("el => el.getBoundingClientRect().toJSON()")
    assert box["width"] > 0 and box["height"] > 0, (
        f"the attached thread's outline hangs on a box of no size: {box}"
    )

    page.locator("[data-lf-for='sug-thistle'] .lf-sug-reject").click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    expect(page.locator("#sug-thistle.lf-mark-el")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_reply_renders_the_markdown_it_was_written_in(browser, serve):
    """A message's text is Markdown, rendered here by the page's own vendored layer —
    the wire carries the log's words and nothing else. Every raw tag renders as the
    characters it was written in: prose says Vec<T>, and swallowing it into an element
    would lose the words in front of the user with nothing saying so. What the
    panel adds is the page's own dress: the theme's element rules are at document level
    and reach in, a fenced block colors from the tokenizer a version's <pre><code>
    uses, and a bare URL arrives as the link the user will want to follow."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "revision": 1,
            "text": "which one wins?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "revision": 1,
            "text": MARKDOWN_REPLY,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    body = page.locator(".lf-msg.claude .lf-msg-body")
    expect(body.locator("li")).to_have_count(2)
    expect(body.locator("strong")).to_have_text("behind")
    expect(body.locator("blockquote")).to_have_text("which one wins?")
    expect(body.locator('pre code [data-lf-syn="kw"]').first).to_have_text("def")
    expect(body.locator('a[href="https://example.com/notes"]')).to_have_count(1)
    # The paragraph's asterisks are gone from the words, not merely hidden, and the
    # raw tag's characters are still among them: what the user can select is what
    # the message says.
    text = body.inner_text()
    assert "**" not in text and "Vec<T>" in text
    assert errors == []
    page.close()


def test_a_message_reference_travels_or_says_it_cant(browser, serve):
    """A message can point at the page with a fragment link, and the platform is what
    carries the reader: collapsed content wears hidden="until-found", so the jump
    fires beforematch and the tab holding the target opens itself. That half is
    pinned here rather than implemented — a runtime that starts intercepting these
    presses has to keep doing it, reveal included.

    The half the browser has no answer for is an id this version hasn't got, which
    needs nobody to have erred: a comment outlives the version it was written on.
    Unmarked it reads live, moves nothing, and leaves a fragment nobody holds in the
    URL for the next load to honor. So it wears the detached face a stranded quote
    wears and its press is refused — asserted from a real press, since that refusal
    is the whole of what the runtime does here."""
    url = serve(REF_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ref",
            "author": "user",
            "revision": 1,
            "text": "See [the bath](#p-bath), not [the old note](#gone).",
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()

    live = page.locator('.lf-msg-body a[href="#p-bath"]')
    expect(live).to_have_attribute("title", "Jump to § p-bath")
    # Collapsed behind the inactive tab until the jump asks for it, which is the
    # platform half: hidden="until-found" answers a fragment navigation.
    hidden = re.compile(".*")
    expect(page.locator("#tab-bath")).to_have_attribute("hidden", hidden)
    live.click()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )

    # The other half of a link: opened in its own tab it is an arrival, which the
    # browser answers before any widget has upgraded — so the runtime is what aims it
    # (landArrival). Nothing of this tab travels with it; the new one starts empty.
    # Which chord opens that tab is the platform's answer rather than one this suite
    # holds — ⌘ where it was written, ⌃ where CI runs it — so the press names the
    # gesture and lets Playwright spell it. Named outright, the Linux press opened
    # nothing at all and the wait for the tab ran its full 30s before saying so.
    tab = opened_tab(page, lambda: live.click(modifiers=["ControlOrMeta"]))
    tab.wait_for_function(BOTH_STAMPS)
    tab.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )
    tab.close()

    dead = page.locator('.lf-msg-body a[href="#gone"]')
    expect(dead).to_have_class("detached")
    expect(dead).to_have_attribute("aria-disabled", "true")
    expect(dead).to_have_attribute(
        "title", "§ gone isn't in the version you're viewing"
    )
    # force, because locator.click refuses aria-disabled controls and that refusal is
    # the state under test. Nothing will happen, so there is no fact to consume: the
    # press is the edge, and the hash the browser would write is synchronous with it.
    at = page.evaluate("() => document.body.scrollTop")
    was = page.url  # the live jump left its own fragment, as a fragment jump does
    dead.click(force=True)
    assert page.url == was, page.url
    assert page.evaluate("() => document.body.scrollTop") == at
    assert errors == []
    page.close()


def test_an_arrival_lands_where_the_url_aimed(browser, serve):
    """A URL naming an element is answered once the page is done becoming itself.

    The browser answers it at parse time, when no widget has upgraded and nothing is
    collapsed yet — so the tab holding the target is still open, the document is
    still its unupgraded height, and both facts stop being true a moment later. The
    same staleness is why scroll restoration is manual; the fragment was the half of
    that takeover never written.

    Then the ranking, which is the browser's own. Arriving somewhere named is what a
    fragment is for, and the reading position this tab kept — of whatever it last
    left this page at — must not paint over it. Returning is the other way round: on
    a reload the fragment is left over from a reference followed earlier, and the
    reader's own position is the answer."""
    url = serve(REF_PAGE)
    hidden = re.compile(".*")
    onscreen = """(id) => { const r = document.getElementById(id).getBoundingClientRect();
                            return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""

    # A fresh tab: nothing saved, nothing to outrank. The target is behind a tab that
    # does not exist until the upgrade runs, which is after the browser has jumped.
    page, errors = open_page(browser, f"{url}#p-bath")
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(onscreen, arg="p-bath")

    # Read to the end and leave: the position is written down on the way out and the
    # tab keeps it. Coming back at a named place is what the ranking is for — that
    # position is real and recent, and still not what this URL asked for.
    page.evaluate("() => document.body.scrollTo({top: 1e6, behavior: 'instant'})")
    page.goto("about:blank")
    page.goto(f"{url}#p-bath")
    page.wait_for_function(BOTH_STAMPS)
    page.wait_for_function(onscreen, arg="p-bath")

    # The reader moves on, so the fragment is stale by the reload that carries it. The
    # bath tab stays open across that reload and says nothing about this — a tab
    # remembers its own panel, the same way the position is remembered here.
    page.evaluate("() => document.body.scrollTo({top: 1e6, behavior: 'instant'})")
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    page.wait_for_function(onscreen, arg="tail-end")
    assert errors == []
    page.close()


def test_a_suggestion_shows_the_characters_it_proposes(browser, serve):
    """A suggestion's words are bound for the page verbatim, so the panel shows them
    as typed. Rendering them would promise the user an italic where the next
    version carries the asterisks they wrote."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "s1",
            "author": "user",
            "revision": 1,
            "suggestion": True,
            "text": "Retry up to *five* times.",
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    body = page.locator(".lf-msg-body.lf-suggest-body")
    expect(body).to_have_text("Retry up to *five* times.")
    expect(body.locator("em")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_reply_widget_replays_and_withdraws_its_action(browser, serve):
    """A widget inside a reply exists only once the panel has rendered the log,
    which is later than everything on the page — so the replay runs at the end of
    a poll, after that render, and an action naming a widget it doesn't find is
    one no version will ever hold (an honored suggestion, whose id the honoring
    version dropped) rather than one to look for again on the next poll. Its authored
    record is banked while the reply body is still detached, so withdrawing the action
    restores that baseline without a version file for the chrome widget."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "revision": 1,
            "text": "Which of these?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP,
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "rp-live",
            "action": "choose",
            "detail": {"options": ["rp-shim"]},
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-comments").click()
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")
    assert page.locator("#rp-live lf-option[chosen]").count() == 1

    # Chrome belongs to the thread rather than the page version. Its action therefore
    # still stands, and is still the reader's newest undoable gesture, after the page
    # advances around the conversation.
    stamp_page(d, REPLY_HOST_PAGE, "v2")
    wait_for_revision(page, 2)
    if not page.locator(".lf-panel").is_visible():
        page.locator(".lf-comments").click()
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")

    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    page.keyboard.press("z")
    round_trip(page)
    assert events_model.read_events(d)[-1]["kind"] == "undo"
    expect(page.locator("#rp-live lf-option[chosen]")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_thread_question_asks_until_answered(browser, serve):
    """A question in a thread is one of the page's asks — a request to the reader
    wherever it stands — and `n` opens the panel to reach it. A single-answer group
    is answered by its pick, as on the page; a `multiple` group's toggles each
    reach the agent live, so only its Done press closes it, as an `answer` action
    the ask stands until (x-awaits.until). The thread's own reply box is the words'
    home, so the group brings no box of its own — and an armed g chord keeps its
    digits even from a mark, because the chord promised a comment.

    The answer is said once, when the log takes it. The log is where it is recorded,
    and the group's own markup stays the author's: a module writes there only where the
    registry declares the attribute as a record form, which a thread verb can never
    have, no version being able to carry a thread's markup."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        events_model.append_event(serve.page_dir, event)
    page, errors = open_page(browser, url)
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (2)")

    page.keyboard.press("n")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator("#tq-one .lf-pick").first).to_be_focused()
    expect(page.locator(".lf-thread .lf-say")).to_have_count(0)
    reply = page.locator(".lf-thread:has(#tq-one) > .lf-compose textarea")
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(page.locator("#tq-one > lf-option[chosen]")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread:has(#tq-one)")).to_be_focused()

    # The group's hairline belongs to the upper neighbour, so the Done press keeps its
    # own frame whole. Drawn by the lower neighbour instead, the divider recolored the
    # press's top edge and left the seam above it to nothing.
    assert page.locator("#tq-set .lf-done").evaluate(
        """el => { const s = getComputedStyle(el);
                   return s.borderTopColor === s.borderBottomColor
                       && s.borderTopWidth === s.borderBottomWidth; }"""
    ), "the group's divider recolors the Done press's own frame"

    # And it butts that hairline, like every other cell of the control. This is the one
    # place the reading is asked at all: the joined-cell readings in the render gate see
    # a served version, and a thread group lives in the panel the runtime builds, so the
    # gate never reaches it. The press was written as a control floating inside the
    # group on a margin of its own, and the theme comment said so — but the group is a
    # grid and had been stretching it to the full column all along, so what the 8px
    # actually drew was a hairline with dead ground under it, on every thread the agent
    # asked a set question in.
    seam = page.locator("#tq-set").evaluate(
        """el => { const done = el.querySelector('.lf-done');
                   const last = done.previousElementSibling;
                   const a = last.getBoundingClientRect();
                   const b = done.getBoundingClientRect();
                   return {gap: Math.round((b.top - a.bottom) * 10) / 10,
                           stretched: Math.abs(a.width - b.width) < 1}; }"""
    )
    assert seam["stretched"], (
        "the Done press no longer fills the column, so what follows is about a shape "
        "this test no longer describes"
    )
    assert seam["gap"] < 0.5, (
        f"the hairline above the Done press floats {seam['gap']}px above it"
    )

    page.locator("#tq-redis").click()
    expect(asks).to_have_text("Asks (1)")

    page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(asks).to_have_text("Asks (1)")
    page.locator("#tq-set .lf-done").click()
    expect(asks).to_be_hidden()
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    # Said once, by the log's answer. An `answered` attribute on the group said it
    # again in the author's namespace, where the entry admits nothing undeclared and no
    # version could ever have carried a record of a thread verb — invisible to every
    # consumer but shallowSigs, which reads what no version can assert as state one
    # authored.
    assert (
        render_checks_model.evaluate_probe(page, "undeclaredAttrs", page_registry(page))
        == []
    ), "the Done press left an attribute on a widget its entry never declared"
    round_trip(page)
    actions = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert actions[-1]["widget"] == "tq-set" and actions[-1]["action"] == "answer"
    assert actions[-1]["detail"] == {}

    # And a second tab reads it off the log, which is the only place it is written.
    # A reader who made no gesture gets the same pressed press and the same closed
    # ask — replay is what puts it there, and the one representation is what replay
    # writes, so there is nothing for a version or a markup copy to fall behind.
    other, other_errors = open_page(browser, url)
    expect(other.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    expect(other.locator(".lf-asks")).to_be_hidden()
    assert (
        render_checks_model.evaluate_probe(
            other, "undeclaredAttrs", page_registry(other)
        )
        == []
    ), "replaying the answer left an attribute the entry never declared"
    assert other_errors == []
    other.close()

    # Taking back a recordless chrome answer rebuilds its authored controls and the
    # same standing projection opens the ask again. The selection is another facet,
    # so it survives that rebuild.
    undo(page)
    expect(asks).to_have_text("Asks (1)")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")

    # The chord's promise holds from a mark: g c then 1 reaches the first thread's
    # reply box, and no pick is sent for the digit the chord took.
    page.locator("#tq-one .lf-pick").first.focus()
    page.keyboard.press("g")
    page.keyboard.press("c")
    page.keyboard.press("1")
    expect(page.locator(".lf-thread textarea").first).to_be_focused()
    sent = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert sent[-1]["action"] == "answer", "the chord's digit must not pick"
    assert errors == []
    page.close()


def test_a_thread_answer_is_not_repainted_after_its_undo_arrives_with_it(
    browser, serve
):
    """The Done press paints only from replay. If one read first reveals both the
    answer and its undo, the send continuation must not overwrite that authoritative
    authored state after replay has accounted for the action."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(serve.page_dir, THREAD_ASKS[1])
    page, errors = open_page(browser, url)
    page.keyboard.press("n")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    done = page.locator("#tq-set .lf-done")
    with page.expect_request("**/api/event"):
        done.click()
    page.wait_for_timeout(0)
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    told(page)
    page.route("**/api/state*", refuse)
    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [("tq-set", "answer")]
    assert errors == []
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")
    page.close()


def test_a_refused_thread_choice_restores_its_frozen_markup(browser, serve):
    """Thread widgets arrive after page startup, but their comment markup is still
    their authored baseline. A definitive refusal removes the optimistic choice from
    that baseline instead of leaving a decision the log never took."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(serve.page_dir, THREAD_ASKS[1])
    page, errors = open_page(browser, url)
    page.keyboard.press("n")
    expect(page.locator(".lf-panel")).to_be_visible()
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    with page.expect_request("**/api/event"):
        page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    assert actions(serve.page_dir) == []
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_refused_thread_choice_replays_recorded_and_recordless_history(
    browser, serve
):
    """A recordless accepted action still belongs to the widget's history.
    Reconstructing after a later refusal must replay both the recorded selection and
    the separate completion facet, retaining both visible facts."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(serve.page_dir, THREAD_ASKS[1])
    page, errors = open_page(browser, url)
    page.keyboard.press("n")
    page.locator("#tq-logs").click()
    round_trip(page)
    page.locator("#tq-set .lf-done").click()
    round_trip(page)
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#tq-metrics").click()
    expect(page.locator("#tq-metrics")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-metrics")).not_to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    assert [
        (event["action"], event["detail"]) for event in actions(serve.page_dir)
    ] == [
        ("choose", {"options": ["tq-logs"]}),
        ("answer", {}),
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_refusal_does_not_paint_a_queued_recordless_thread_action(browser, serve):
    """The outbox is delivery order, not wholly an optimistic overlay. A recorded
    choice is already painted, but the record-less Done press waits for acceptance;
    correcting the older choice must not paint that queued press early."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(serve.page_dir, THREAD_ASKS[1])
    page, errors = open_page(browser, url)
    page.keyboard.press("n")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#tq-logs").click()
    done = page.locator("#tq-set .lf-done")
    done.click()
    expect(done).to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")

    first_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": first_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    expect(done).to_have_attribute("aria-pressed", "false")
    second_attempt = held[1].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[1].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": second_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert actions(serve.page_dir) == []
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_done_press_says_it_is_waiting_and_answers_once(browser, serve):
    """The Done press waits for the log the way a suggestion's decision does, so it
    owes the reader what every waiting press owes: `aria-busy` while the answer is in
    the wire, and the pressed state only once the log has taken it. Nothing said the
    press had landed before this, and a `button` styled by the theme gets no `:active`
    of its own, so the reader had the round trip with no answer of any kind.

    One press is one `answer` action, which this group's own comment has always
    claimed and nothing checked. A second press cannot be caught in the wire — `post`
    sends one action at a time, so it never reaches the route — so what it would leave
    is a second line in the log once the queue drains, and that is where this reads it.
    """
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        events_model.append_event(serve.page_dir, event)
    page, errors = open_page(browser, url)
    page.keyboard.press("n")
    expect(page.locator(".lf-panel")).to_be_visible()
    done = page.locator("#tq-set .lf-done")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    done.click()
    _until(page, lambda traffic: traffic.sends == 1, "held the answer in the wire")

    expect(done).to_have_attribute("aria-busy", "true")
    # The press is acknowledged; the answer it asks for is not painted, the log not
    # having taken it yet.
    expect(done).to_have_attribute("aria-pressed", "false")
    done.click()
    done.click()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(done).to_have_attribute("aria-pressed", "true")
    expect(done).not_to_have_attribute("aria-busy", "true")
    assert [
        (e["widget"], e["action"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("tq-set", "answer")]
    assert errors == []
    page.close()


def test_closing_a_thread_withdraws_the_question_in_it(browser, serve):
    """A question in a thread is the thread's, so closing the thread takes the ask
    with it. The group is still there to read in the disclosure, and still holds no
    answer — what went is the page's claim on the reader, who would otherwise carry a
    standing ask for the life of the page and have `n` step them into a closed
    disclosure to reach it."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(serve.page_dir, THREAD_ASKS[0])
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-asks")).to_have_text("Asks (1)")

    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "claude", "parent": "c-which"}
    )
    told(page)
    expect(page.locator(".lf-asks")).to_be_hidden()
    expect(page.locator(".lf-details #tq-one")).to_have_count(1)
    expect(page.locator("#tq-redis")).not_to_have_attribute("chosen", "")
    assert errors == []
    page.close()


def test_agent_places_its_live_line_before_command_evidence(browser, serve):
    command = leaf_page(
        "worker evidence",
        """
<lf-roster id="team">
  <lf-agent id="worker" state="working"><strong>worker</strong> Owns the remit.
    <lf-worktree id="proof" source="atlas-worktrees"></lf-worktree>
  </lf-agent>
</lf-roster>
""",
    )
    page, errors = open_page(browser, serve(command))

    assert page.locator("#worker").evaluate(
        """worker => [...worker.children].map(child => child.classList.contains('lf-agent-line')
          ? 'line' : child.id).filter(Boolean)"""
    ) == ["line", "proof"]
    assert errors == []
    page.close()


def test_command_goal_can_pause_after_an_ordinary_conversation_started(browser, serve):
    """A normal note does not consume the goal's stronger pause door. The reader
    can start a later held thread, whose root remains the one atomic hold fact."""
    page, errors = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    goal = page.locator("#goal-parser")
    conversation = goal.locator(":scope > .lf-conversation")
    first = conversation.locator(":scope > .lf-say")
    first.get_by_role("textbox").fill("Keep parsing; this is only a note.")
    first.get_by_role("button", name="Send", exact=True).click()
    round_trip(page)

    expect(first).to_be_visible()
    first.get_by_role("textbox").fill("Finish the hunk, then park.")
    first.get_by_role("button", name="Send & pause", exact=True).click()
    round_trip(page)

    expect(goal).to_have_attribute("data-lf-held")
    roots = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    assert [(event["text"], event.get("holds")) for event in roots] == [
        ("Keep parsing; this is only a note.", None),
        ("Finish the hunk, then park.", "goal-parser"),
    ]
    assert errors == []
    page.close()


def test_command_goal_conversation_follows_its_declaration_not_talk(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    registry = json.loads((COMMAND_HUB_PACKAGE / "registry.json").read_text())
    task = registry["lf-task"]
    task["properties"]["consult"] = {"type": "boolean"}
    task["x-conversation"] = {
        "when": {"consult": [True]},
        "hold": "pause",
    }
    project = tmp_path / ".leaf"
    project.mkdir()
    (project / "registry.json").write_text(json.dumps({"lf-task": task}))
    command = leaf_page(
        "custom goal",
        """<lf-command id="hub">
  <lf-task id="goal" status="active" consult><strong>Custom goal</strong></lf-task>
</lf-command>""",
    )
    url = serve(command)
    page, errors = open_page(browser, url)
    conversation = page.locator("#goal > .lf-conversation")
    expect(
        conversation.get_by_role("textbox", name="Say something here")
    ).to_be_visible()
    expect(conversation.get_by_role("button", name="pause", exact=True)).to_be_visible()
    assert errors == []
    page.close()


def test_command_hub_an_absorbed_input_stays_fulfilled(browser, serve):
    """An input action discharges the request live; the honoring version removes its
    authored `needed` condition, so clearing record debt cannot turn the input back into
    an ask."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    draft = page.locator("#ledger-cargo")
    draft.get_by_role("button", name="Edit ledger-cargo").click()
    provided = "ledger_id,amount\n7,42"
    draft.get_by_role("textbox", name="Edit ledger-cargo").fill(provided)
    draft.get_by_role("button", name="Save").click()
    round_trip(page)
    expect(page.get_by_role("button", name="Asks (4)")).to_be_visible()

    honoring = re.sub(
        r'<lf-draft id="ledger-cargo" needed>.*?</lf-draft>',
        f'<lf-draft id="ledger-cargo"><pre>\n{provided}\n</pre></lf-draft>',
        COMMAND_HUB_PAGE,
        flags=re.DOTALL,
    )
    stamp_page(d, honoring, "input absorbed")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)
    expect(page.get_by_role("button", name="Asks (4)")).to_be_visible()
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("needed")
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("data-lf-pending")
    expect(page.locator("#ledger-fixture > .lf-task-meta")).not_to_contain_text(
        "privileged input"
    )
    assert errors == []
    page.close()


def test_command_hub_an_absorbed_intervention_does_not_stop_again(browser, serve):
    """Pending paint is record debt, not whether an intervention is answered. Once a
    version carries the standing choice, the goal stays dispositioned even though its
    provisional mark correctly leaves."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    page.locator("#dedupe-snooze").get_by_role(
        "checkbox", name=re.compile("choose one: Park it for tomorrow")
    ).click()
    round_trip(page)
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("4 stopped")

    recorded = COMMAND_HUB_PAGE.replace(
        '<lf-option id="dedupe-snooze" for="parser-dedupe">',
        '<lf-option id="dedupe-snooze" for="parser-dedupe" chosen>',
    )
    stamp_page(d, recorded, "recorded snooze")
    wait_for_revision(page, 2)
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("4 stopped")
    expect(page.locator("#hub-plan > .lf-stopped-view")).not_to_contain_text(
        "Deduplicate the corpus snapshot"
    )
    expect(page.locator("#dedupe-snooze")).not_to_have_attribute("data-lf-pending")
    expect(page.locator("#parser-dedupe > .lf-task-meta")).not_to_contain_text(
        "decision"
    )
    assert errors == []
    page.close()


def test_command_hub_derives_the_operator_reading_from_its_goal_tree(browser, serve):
    """G's primary contract: one plan supplies progress, stopped work, live
    workers, and worktree evidence. A worker report moves that reading rather than
    updating a second dashboard copy."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    stale_report(d, "w-2", "stalled without a new commit", 3)
    page, errors = open_page(browser, url)
    head = page.locator("#hub-plan > .lf-command-head")
    expect(head).to_contain_text("7/18 leaves")
    expect(head).to_contain_text("4 running")
    expect(head).to_contain_text("5 workers")
    expect(head).to_contain_text("1 quiet")
    expect(head).to_contain_text("5 stopped")
    expect(page.get_by_role("button", name="Asks (5)")).to_be_visible()
    expect(page.locator("#hub-plan > .lf-fleet-view")).to_contain_text(
        "Fleet · 5 live workers"
    )
    expect(page.locator("#hub-plan > .lf-fleet-view li")).to_have_count(5)
    expect(page.locator("#hub-plan > .lf-fleet-view")).not_to_contain_text("w-5")
    expect(page.locator("#hub-plan > .lf-command-head a")).to_have_count(4)
    expect(
        page.locator(
            "#hub-plan > .lf-command-head a:not([data-lf-offer][data-lf-said])"
        )
    ).to_have_count(0)
    expect(
        page.locator(
            "#hub-plan > :is(.lf-stopped-view, .lf-fleet-view) > "
            "summary:not([data-lf-offer][data-lf-said])"
        )
    ).to_have_count(0)

    coordinator = page.locator("#atlas-lead")
    expect(coordinator).to_be_visible()
    head.get_by_role("link", name="4 running").click()
    expect(coordinator).to_be_visible()
    workers = page.locator("#goal-parser > lf-agent")
    expect(workers.first).to_be_hidden()
    page.locator("#goal-parser > .lf-task-meta .lf-task-crew").click()
    expect(workers).to_have_count(1)
    expect(page.locator("#w-5")).to_have_attribute("state", "reaped")
    expect(workers.first).to_be_visible()
    worktree = page.locator("#tree-w-1")
    expect(worktree.locator("#lf-tree-w-1-diff")).to_be_hidden()
    worktree_head = worktree.locator(
        ":scope > .lf-worktree-snapshot > .lf-worktree-head"
    )
    worktree_head.click()
    expect(worktree.locator("#lf-tree-w-1-diff")).to_be_visible()
    worktree_head.focus()
    page.keyboard.press("Enter")
    expect(worktree.locator("#lf-tree-w-1-diff")).to_be_hidden()
    expect(worktree_head).to_be_focused()
    page.keyboard.press("Enter")
    expect(worktree.locator("#lf-tree-w-1-diff")).to_be_visible()
    expect(worktree_head).to_be_focused()

    sent = CliRunner().invoke(
        cli_model.cli, ["report", str(d), "api-errors", "status", "status=done"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(head).to_contain_text("8/18 leaves")
    expect(page.locator("#goal-api > .lf-task-meta")).to_contain_text("1/3")

    page.locator("#goal-parser > .lf-task-meta .lf-task-crew").click()
    expect(workers.first).to_be_hidden()
    page.emulate_media(media="print")
    expect(workers.first).to_be_visible()
    expect(worktree.locator("#lf-tree-w-1-diff")).to_be_visible()
    expect(worktree_head).to_contain_text("atlas/xml-declarations")
    page.emulate_media(media="screen")

    resized(page, 390, 900)
    assert page.evaluate(
        "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    assert errors == []
    page.close()


def test_command_hub_disposition_refolds_stopped_work(browser, serve):
    """The stopped reading is derived, not a second list to maintain. Recording a stall
    disposition removes that goal from the oldest-first reading; undo restores the
    same goal, order, and blast-radius evidence from the standing log."""
    url = serve(COMMAND_HUB_EXAMPLE)
    page, errors = open_page(browser, url)
    stopped = page.locator("#hub-plan > .lf-stopped-view")
    stopped.locator("summary").click()
    page.evaluate("""() => {
      for (const goal of document.querySelectorAll('[stopped-at]'))
        goal.setAttribute('stopped-at', '2030-01-01T00:00:00Z');
      document.getElementById('schema-choice')
        .setAttribute('stopped-at', '2026-08-21T08:00:00+02:00');
      document.getElementById('api-shape')
        .setAttribute('stopped-at', '2026-08-21T07:00:00-07:00');
    }""")
    expect(stopped.locator("li").first).to_contain_text("Choose the additive schema")
    expect(stopped).to_contain_text("Deduplicate the corpus snapshot")

    page.locator("#dedupe-snooze").get_by_role(
        "checkbox", name=re.compile("choose one: Park it for tomorrow")
    ).click()
    round_trip(page)
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("4 stopped")
    expect(stopped).not_to_contain_text("Deduplicate the corpus snapshot")
    expect(page.locator("#atlas-record")).to_contain_text(
        "Selected: Park it for tomorrow"
    )

    page.keyboard.press("z")
    round_trip(page)
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("5 stopped")
    expect(stopped).to_contain_text("Deduplicate the corpus snapshot")
    assert errors == []
    page.close()


def test_command_hub_goal_metadata_wraps_on_a_phone(browser, serve):
    long_when = "handoff-" + "unbroken" * 40
    markup = COMMAND_HUB_PAGE.replace('when="week 3"', f'when="{long_when}"', 1)
    page, errors = open_page(browser, serve(markup))
    resized(page, 390, 900)

    expect(page.locator("#goal-parser > .lf-task-meta")).to_contain_text(long_when)
    assert page.evaluate(
        "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    assert errors == []
    page.close()


def test_command_hub_input_is_trimmed_before_it_enters_the_record(browser, serve):
    """The replica cargo is visible in the real editor before Save. Trimming it
    changes the one payload that enters the log, leaves a receipt naming the input,
    and releases that input row without claiming the dependent work completed."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    draft = page.locator("#ledger-cargo")
    draft.get_by_role("button", name="Edit ledger-cargo").click()
    editor = draft.get_by_role("textbox", name="Edit ledger-cargo")
    editor.fill(
        "ledger_id,customer_name,billing_email,amount\n7,Alice,a@example.test,42"
    )
    assert not [
        event
        for event in events_model.read_events(d)
        if event.get("widget") == "ledger-cargo"
    ]
    editor.fill(
        "ledger_id,customer_name,billing_email,amount\n7,[redacted],[redacted],42"
    )
    draft.get_by_role("button", name="Save").click()
    round_trip(page)

    edit = next(
        event
        for event in reversed(events_model.read_events(d))
        if event.get("widget") == "ledger-cargo"
    )
    assert "Alice" not in edit["detail"]["text"]
    assert "a@example.test" not in edit["detail"]["text"]
    assert edit["detail"]["text"].count("[redacted]") == 2
    expect(page.locator("#atlas-record")).to_contain_text("ledger-cargo")
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("4 stopped")
    expect(page.locator("#ledger-variance")).to_have_attribute("status", "planned")
    assert errors == []
    page.close()


def test_command_hub_keeps_a_real_goal_ask_outside_a_quoted_decision(browser, serve):
    """An exhibited choice is inert evidence. It cannot answer the blocked goal
    containing it, nor suppress that goal merely because it declares x-awaits."""
    command = """<lf-command id="hub-plan" label="Quoted ask">
      <lf-task id="goal" status="blocked" stopped-at="2026-08-21T08:00:00Z">
        <strong>Blocked goal</strong>
        <lf-specimen id="sample"><lf-options id="example" choose>
          <lf-option id="example-a"><strong>Example only</strong></lf-option>
        </lf-options></lf-specimen>
      </lf-task>
    </lf-command>"""
    html = re.sub(
        r"<lf-command\b.*?</lf-command>",
        command,
        COMMAND_HUB_PAGE,
        count=1,
        flags=re.DOTALL,
    )
    page, errors = open_page(browser, serve(html))
    expect(page.get_by_role("button", name="Asks (1)")).to_be_visible()
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("1 stopped")
    expect(page.locator("#hub-plan > .lf-stopped-view")).to_contain_text("Blocked goal")
    assert errors == []
    page.close()


def test_command_hub_keeps_projection_focus_when_unrelated_news_arrives(browser, serve):
    page, errors = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    fleet = page.locator("#hub-plan > .lf-fleet-view")
    fleet.locator(":scope > summary").click()
    worker = fleet.get_by_role("link", name="w-1", exact=True)
    worker.focus()
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "w-2",
            "state",
            "state=waiting",
            "doing=parked for review",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(worker).to_be_focused()

    summary = fleet.locator(":scope > summary")
    summary.focus()
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "report",
            str(d),
            "w-2",
            "state",
            "state=blocked",
            "doing=waiting on evidence",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(summary).to_be_focused()
    assert errors == []
    page.close()


def test_command_hub_repaints_anchors_after_generated_projections_change(
    browser, serve
):
    page, errors = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    # The worktree head is a generated passage. Its disclosure arrow and the Command
    # projection can change without invalidating the branch fact the comment named.
    expect(page.locator("#goal-parser > .lf-task-meta .lf-task-crew")).to_be_visible()
    page.locator("#goal-parser > .lf-task-meta .lf-task-crew").click()
    head = page.locator("#tree-w-1 > .lf-worktree-snapshot > .lf-worktree-head")
    head.evaluate(
        """(el) => {
          const quote = 'atlas/xml-declarations';
          const at = el.firstChild.data.indexOf(quote);
          const range = document.createRange();
          range.setStart(el.firstChild, at); range.setEnd(el.firstChild, at + quote.length);
          const selection = getSelection(); selection.removeAllRanges();
          selection.addRange(range);
          document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        }"""
    )
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill("Keep this branch evidence visible.")
    page.get_by_role("button", name="Comment", exact=True).click()
    round_trip(page)
    sent = CliRunner().invoke(
        cli_model.cli,
        ["report", str(d), "goal-parser", "status", "status=review"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    head.click()
    page.wait_for_function(
        """() => [...(CSS.highlights.get('lf-mark') ?? [])]
          .some(range => range.toString().includes('atlas/xml-declarations'))"""
    )
    assert "atlas/xml-declarations" in painted(page, "lf-mark")
    assert errors == []
    page.close()


def test_command_hub_reveals_collapsed_worker_evidence_from_threads(browser, serve):
    url = serve(COMMAND_HUB_EXAMPLE)
    threads = {
        target: events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {target}.",
                "anchor": {"section": target},
            },
        )["id"]
        for target in ("w-1", "lf-tree-w-1-diff")
    }
    page, errors = open_page(browser, url)
    # Initial anchor painting already reveals its evidence. Close both disclosures
    # again so the quote gesture, rather than page startup, is the single changed
    # factor in this journey.
    page.evaluate(
        """() => {
          document.querySelector('#goal-parser').removeAttribute('data-lf-open');
          document.querySelector('#tree-w-1').removeAttribute('data-lf-open');
        }"""
    )
    expect(page.locator("#w-1")).to_be_hidden()
    page.locator(".lf-comments").click()
    page.locator(f'.lf-thread[data-id="{threads["w-1"]}"] .lf-quote').click()
    expect(page.locator("#w-1")).to_be_visible()
    expect(page.locator("#lf-tree-w-1-diff")).to_be_hidden()
    page.locator(
        f'.lf-thread[data-id="{threads["lf-tree-w-1-diff"]}"] .lf-quote'
    ).click()
    expect(page.locator("#lf-tree-w-1-diff")).to_be_visible()
    expect(
        page.locator("#tree-w-1 > .lf-worktree-snapshot > .lf-worktree-head")
    ).to_have_attribute("aria-expanded", "true")
    assert errors == []
    page.close()


def test_command_hub_send_and_pause_is_one_thread_fold(browser, serve):
    """The stronger send has no companion pause action. Its unresolved thread is
    the hold, so a reply preserves it, resolution releases it, and undoing that
    resolution restores it with the same evidence and comment id."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    goal = page.locator("#goal-parser")
    conversation = goal.locator(":scope > .lf-conversation")
    conversation.get_by_role("textbox").fill("Finish the current hunk, then park here.")
    conversation.get_by_role("button", name="Send & pause", exact=True).click()
    round_trip(page)
    expect(goal).to_have_attribute("data-lf-held")
    expect(goal.locator(":scope > .lf-task-meta")).to_contain_text("paused by you")
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("6 stopped")
    expect(page.locator("#atlas-record")).to_contain_text(
        "sent and paused · Replace the XML parser (goal-parser)"
    )
    root = next(
        event
        for event in events_model.read_events(d)
        if event.get("holds") == "goal-parser"
    )

    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Relay",
            "parent": root["id"],
            "revision": 1,
            "text": "The hunk is complete; the worker is parked.",
        },
    )
    told(page)
    expect(goal).to_have_attribute("data-lf-held", root["id"])

    page.get_by_role("button", name=re.compile("^Comments")).click()
    page.locator(f'.lf-thread[data-id="{root["id"]}"]').get_by_role(
        "button", name="Resolve", exact=True
    ).click()
    round_trip(page)
    expect(goal).not_to_have_attribute("data-lf-held")
    expect(page.locator("#hub-plan > .lf-command-head")).to_contain_text("5 stopped")

    page.keyboard.press("z")
    round_trip(page)
    expect(goal).to_have_attribute("data-lf-held", root["id"])
    assert [
        event["kind"]
        for event in events_model.read_events(d)
        if event["kind"] in {"comment", "resolve", "undo"}
    ] == ["comment", "resolve", "undo"]
    assert errors == []
    page.close()


def test_command_hub_stopped_age_does_not_cross_an_active_publication(browser, serve):
    """Two stopped reports are not proof of one continuous stop. An honoring
    publication can absorb the first, and a later version can author active work;
    a fresh stopped report dates the new interruption from itself."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "revision": 1,
            "widget": "parser-dedupe",
            "action": "status",
            "detail": {"status": "stalled"},
            "ts": (datetime.now().astimezone() - timedelta(hours=3)).isoformat(),
        },
    )
    stamp_page(d, COMMAND_HUB_PAGE, "absorbed stop")
    active = re.sub(
        r'(<lf-task\s+id="parser-dedupe"\s+)status="stalled"',
        r'\1status="active"',
        COMMAND_HUB_PAGE,
    )
    assert active != COMMAND_HUB_PAGE
    stamp_page(d, active, "work resumed")
    events_model.append_event(
        d,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "revision": 3,
            "widget": "parser-dedupe",
            "action": "status",
            "detail": {"status": "stalled"},
            "ts": datetime.now().astimezone().isoformat(),
        },
    )

    latest = url.replace("/versions/v1.html", "/")
    page, errors = open_page(browser, latest)
    expect(page.locator(".lf-version")).to_contain_text("v3")
    assert "/versions/" not in page.url
    row = page.locator(
        "#hub-plan > .lf-stopped-view li", has_text="Deduplicate the corpus snapshot"
    )
    expect(row).to_contain_text("0m")
    expect(row).not_to_contain_text("3h")
    assert errors == []
    page.close()


def test_command_hub_stops_listening_after_live_version_replacement(browser, serve):
    """A command removed with the old main cannot emit another projection."""
    url = serve(COMMAND_HUB_EXAMPLE)
    page, errors = open_page(browser, live_url(url))
    page.evaluate("window.__retiredCommand = document.querySelector('#hub-plan')")
    (serve.page_dir / "versions" / "v2.html").write_text(COMMAND_HUB_PAGE)
    stamp_version_file(serve.page_dir, 2, "same plan")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.evaluate(
        """() => {
          window.__retiredUpdates = 0;
          document.addEventListener("lf-command-update", event => {
            if (event.detail.plan === window.__retiredCommand)
              window.__retiredUpdates += 1;
          });
        }"""
    )

    retired_updates = page.evaluate(
        """async () => {
          window.__retiredCommand.querySelector('#api-errors')
            .setAttribute('status', 'done');
          await new Promise(resolve => requestAnimationFrame(resolve));
          return window.__retiredUpdates;
        }"""
    )

    assert retired_updates == 0
    assert errors == []
    page.close()


def test_command_record_resolves_a_thread_through_any_of_its_messages(browser, serve):
    page, errors = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    root = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Finish the hunk, then park.",
            "anchor": {"section": "goal-parser"},
            "holds": "goal-parser",
        },
    )
    reply = events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": root["id"],
            "revision": 1,
            "text": "The hunk is ready.",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "resolve",
            "author": "user",
            "parent": reply["id"],
            "revision": 1,
        },
    )

    told(page)

    expect(page.locator("#atlas-record")).to_contain_text(
        "Released · Replace the XML parser (goal-parser)"
    )
    assert errors == []
    page.close()


def test_nested_command_projections_stop_at_their_own_boundary(browser, serve):
    command = leaf_page(
        "nested command boundaries",
        """
<lf-command id="outer" label="Outer plan">
  <lf-task id="outer-goal" status="active"><strong>Outer goal</strong>
    <lf-agent id="outer-worker" state="idle"><strong>outer-worker</strong></lf-agent>
    <lf-command id="inner" label="Inner plan">
      <lf-agent id="inner-worker" state="working"><strong>inner-worker</strong></lf-agent>
      <lf-task id="inner-goal" status="done"><strong>Inner goal</strong></lf-task>
    </lf-command>
  </lf-task>
</lf-command>
""",
    )

    page, errors = open_page(browser, serve(command))

    expect(page.locator("#outer > .lf-command-head")).to_contain_text("0/1 leaves")
    expect(page.locator("#outer > .lf-command-head")).to_contain_text("1 workers")
    expect(page.locator("#inner > .lf-command-head")).to_contain_text("1/1 leaves")
    expect(page.locator("#inner > .lf-command-head")).to_contain_text("1 running")
    expect(page.locator("#outer-goal")).not_to_have_attribute("data-lf-open", "")
    page.locator("#inner > .lf-command-head").click(position={"x": 5, "y": 5})
    page.locator("#inner > .lf-fleet-view summary").click()
    page.get_by_role("link", name="inner-worker", exact=True).click()
    expect(page.locator("#outer-goal")).not_to_have_attribute("data-lf-open", "")
    assert errors == []
    page.close()


def test_project_widget_can_join_the_orchestration_projection(
    browser, serve, tmp_path, monkeypatch
):
    """A project adds its own goal tag through the orchestration role map, with no
    Command-specific declaration or change to Leaf's kernel."""
    monkeypatch.chdir(tmp_path)
    registry = {
        "lf-area": {
            "description": "A project-specific Command goal.",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "phase": {"enum": ["active", "blocked", "done"]},
            },
            "required": ["id", "phase"],
            "additionalProperties": False,
            "x-parent": ["lf-command", "lf-area"],
            "x-content": "prose",
            "x-awaits": {"when": {"phase": ["blocked"]}},
            "x-upgrade": False,
        },
        "$command": {
            "widgets": {
                "lf-area": {
                    "role": "goal",
                    "state": "phase",
                    "done": ["done"],
                    "stopped": ["blocked"],
                }
            }
        },
    }
    project = tmp_path / ".leaf"
    project.mkdir()
    (project / "registry.json").write_text(json.dumps(registry))
    command = leaf_page(
        "project command goal",
        """
<lf-command id="hub" label="Project plan" phase="planning">
  <lf-area id="custom-goal" phase="blocked">
    <strong>Custom project goal</strong> Waiting for a project decision.
    </lf-area>
</lf-command>
""",
    )
    url = serve(command)

    page, errors = open_page(browser, url)

    expect(page.locator("#hub > .lf-command-head")).to_contain_text("0/1 leaves")
    expect(page.locator("#hub > .lf-command-head")).to_contain_text("1 stopped")
    expect(page.locator("#hub > .lf-stopped-view")).to_contain_text(
        "Custom project goal"
    )
    expect(page.get_by_role("button", name="Asks (1)")).to_be_visible()
    assert errors == []
    page.close()
