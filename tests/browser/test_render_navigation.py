"Comment marks, Go-to addresses, keyboard navigation, the feature gallery's\njourneys through its tabs and the core surfaces, and the keys each element names as\nthe user moves through the examples."

import re

import pytest
from interact_support import append_carried_log_record
from journeys.test_render_navigation import go_to_passage
from playwright.sync_api import expect
from render_cases_interaction import (
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    live_url,
)
from render_cases_navigation import (
    address_code,
    go_to_address,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLES,
    RELEASE_FOCUS,
    expect_comment_notes,
    leaf_page,
    open_page,
    opened_tab,
    pane_scroll_behavior,
    resized,
    scroll_settled,
    told,
)

from leaf import server as server_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_each_comparison_result_keeps_its_own_comment_destination(browser, serve):
    """Each policy owns a separate anchor and pane-local return route."""
    example = next(e for e in CORPUS_SOURCES if e.stem == "current-proposed-comparison")
    page = open_page(
        browser,
        serve(
            example,
            anchored=[
                (
                    "comparison-current-behavior",
                    "starts its own credential refresh",
                ),
                (
                    "comparison-proposed-behavior",
                    "Other calls in that tab wait for it",
                ),
            ],
        ),
    )
    resized(page, 1600, 700)
    pane_scroll_behavior(page, page.locator("#comparison-current"), "bounded")
    current = page.locator("#comparison-current > :not(header, footer)")
    proposed = page.locator("#comparison-proposed > :not(header, footer)")
    expect(page.locator(".lf-mark-note")).to_have_count(2)
    expect_comment_notes(page, "#comparison-current", 1)
    expect_comment_notes(page, "#comparison-proposed", 1)
    initial_scrolls = page.evaluate("""() => {
        const panes = ["comparison-current", "comparison-proposed"].map(id =>
            document.querySelector(`#${id} > :not(header, footer)`));
        for (const pane of panes) pane.scrollTop = pane.scrollHeight;
        return panes.map(pane => pane.scrollTop);
    }""")
    assert min(initial_scrolls) > 0

    go_to_passage(page, serve.page_dir, "starts its own credential refresh")
    expect(page.locator("#comparison-current-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-current > :not(header, footer)")
    current_after_current = current.evaluate("el => el.scrollTop")
    proposed_after_current = proposed.evaluate("el => el.scrollTop")
    assert current_after_current < initial_scrolls[0]
    assert proposed_after_current == initial_scrolls[1]

    go_to_passage(page, serve.page_dir, "Other calls in that tab wait for it")
    expect(page.locator("#comparison-proposed-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-proposed > :not(header, footer)")
    assert proposed.evaluate("el => el.scrollTop") < proposed_after_current
    assert current.evaluate("el => el.scrollTop") == current_after_current


def test_the_pr_walkthrough_exercises_an_inline_diff_thread(browser, serve):
    """The diff package's worked page carries a real line thread through both seats."""
    source = next(example for example in EXAMPLES if example.stem == "pr-walkthrough")
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
    thread = diff.locator(f'.lf-page-thread[data-thread="{root["id"]}"]')
    expect(thread).to_contain_text(
        "Keep this review note beside the line that changes it."
    )
    send = thread.locator(".lf-compose-submit")
    expect(send).to_be_disabled()
    expect(thread.get_by_role("textbox", name="Reply", exact=True)).to_be_visible()
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
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{prose["id"]}"]')
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
    walked = card.locator(".lf-page-thread").get_attribute("data-thread")
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
    expect(card.locator(f'.lf-page-thread[data-thread="{walked}"]')).to_be_focused()
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
    # A page command that lands in a card scrolled away brings its cluster, and the
    # card, back.
    page.keyboard.press("c")
    reply = card.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_focused()
    page.wait_for_function(shown)
    # So does moving on from one of its controls to the next, as the browser reveals
    # the control a Tab reaches.
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
    reply.evaluate(
        """async (box) => {
          const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          while (box.getBoundingClientRect().top >= 0) {
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


def test_thread_navigation_lands_after_resizing_an_open_reply(browser, serve):
    """A reply open in a card goes on in the floating panel once the window narrows to a
    phone's, and the walk back lands in the panel's view of the previous thread, with
    its reply in view."""
    page = open_page(
        browser,
        live_url(serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)),
    )
    resized(page, 1280, 720)
    card = page.locator(".lf-margin-preview")
    thread = card.get_by_role("group", name="Thread, Is lunch provided", exact=False)
    # The walk reaches the lunch thread wherever the walk's order puts it.
    for _ in range(3):
        page.keyboard.press("t")
        scroll_settled(page)
        if thread.count() and thread.evaluate("el => el === document.activeElement"):
            break
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(
        card.get_by_role("group", name="Thread, Workshop room photo")
    ).to_be_focused()
    scroll_settled(page)
    page.keyboard.press("Enter")
    expect(page.get_by_role("textbox", name="Reply", exact=True)).to_be_focused()
    resized(page, 390, 844)
    scroll_settled(page)
    expect(card).to_be_hidden()
    reply = page.locator(".lf-fp-field leaf-text")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+t")
    view = page.locator(".lf-fp-view:not([data-leaving])")
    expect(view).to_be_focused()
    expect(view).to_contain_text("Is lunch provided")
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    scroll_settled(page)
    expect(reply).to_be_in_viewport(ratio=1)


def test_an_addressed_link_leaves_the_user_at_its_destination(
    browser, serve, other_leaf, one_user
):
    """A generated link hint completes the navigation step it names.

    A fragment lands focus on its target, so the user does not remain at the place they
    left. An external link keeps its new-tab behavior and names that context change even
    though the sequence activates the link without first moving focus through it."""
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
<p><a id="external" href="{destination}" aria-label="Leaf guide">Open the guide</a>.</p>
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


def test_an_external_link_says_and_opens_where_it_goes(
    browser, serve, other_leaf, one_user
):
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

    expect(external).to_have_attribute("target", "_blank")
    expect(external).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source opens in a new tab")
    # The treatment stands inside the link, so the paragraph ends where it was written.
    expect(page.locator("#external ~ *")).to_have_count(0)
    expect(external).to_have_attribute("data-lf-external", "")
    mark = external.evaluate("""link => {
      const style = getComputedStyle(link, '::after');
      return {display: style.display, width: parseFloat(style.width), mask: style.maskImage};
    }""")
    assert mark["display"] == "inline-block"
    assert mark["width"] > 0
    assert "data:image/svg+xml" in mark["mask"]
    expect(page.locator("#fragment")).not_to_have_attribute("data-lf-external", "")
    expect(page.locator("#fragment")).not_to_have_attribute("target", "_blank")
    expect(page.locator("#svg-external")).not_to_have_attribute("data-lf-external", "")
    expect(page.locator("#svg-external")).not_to_have_attribute("target", "_blank")

    tab = opened_tab(page, destination, external.click)
    expect(tab).to_have_url(f"{other_url}/")
    expect(page).to_have_url(url.split("?", 1)[0])


import pytest
from render_cases_interaction import (
    PANEL_PAGE,
    answered_comment,
    panel_comment,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    CHIPS,
    address_codes,
)
from render_harness import (
    PANEL,
    PANEL_THREAD,
    command_reference_rows,
    expect_open_threads,
    expect_panel_says,
    navigate,
    panel_says,
    panel_settled,
    panel_view,
    round_trip,
)


@pytest.mark.shifts_unsurveyed
@pytest.mark.parametrize("viewport", [(1440, 900), (390, 844)])
def test_pr_walkthrough_navigation_starts_the_review_at_every_width(
    browser, serve, viewport
):
    """Contents must be available before the reader works through this long review.

    The former sidebar placed the outline after the complete PR facts and history;
    when the tracks stacked, it also came after the entire article. The authored
    reading order now puts navigation first and supporting evidence in the article.
    """
    source = next(example for example in EXAMPLES if example.stem == "pr-walkthrough")
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


@pytest.mark.shifts_unsurveyed
def test_a_panel_thread_closes_with_the_panel_as_go_to_threads_does(browser, serve):
    """A thread with no page destination opens in the panel and Escape puts it away;
    Go-to's Threads opens the panel's list and puts it away the same way."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "This thread has no page anchor.")
    panel_comment(serve.page_dir, "Another panel thread.")
    page = open_page(browser, url)
    view = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    threads = page.locator(panel_view("threads"))

    page.keyboard.press("t")
    expect(view).to_be_focused()
    # Threads, from the thread the user is located in, opens on that thread's row.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(threads.locator(f'.lf-fp-thread[data-key="{root}"]')).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # From the page, Threads holds focus itself.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(threads).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # g T puts away the Threads it opened, as Escape does.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(threads).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)


@pytest.mark.shifts_unsurveyed
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
    filters = goto.locator('[role=row][data-lf-command^="navigation.target.filter."]')
    assert filters.evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          keys: [...row.querySelectorAll('kbd')].map(key => key.textContent),
          action: row.querySelector('.lf-command-reference-command').textContent,
        }))"""
    ) == [
        {
            "command": "navigation.target.filter.margin-entries",
            "keys": ["g", "m"],
            "action": "Show only visible margin targets",
        },
        {
            "command": "navigation.target.filter.threads",
            "keys": ["g", "t"],
            "action": "Show only visible Thread controls",
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
    target_help = goto.locator('[role=row][data-lf-command="navigation.target"]')
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
    filtered = page.locator(CHIPS)
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
    page.locator("#opts-decision").evaluate(
        "node => document.scrollingElement.scrollTo(0, node.offsetTop)"
    )
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).not_to_be_in_viewport()
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(".lf-live")).to_have_text("No visible hyperlinks.")
    expect_panel_says(page, "No visible hyperlinks.")
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
          (await window.__lfWidgetApi())
            .notice('Agent replied — open Threads', {background: true});
        }"""
    )
    expect(page.locator(".lf-live")).to_have_text("Agent replied — open Threads")
    # The empty filter's word stands in the panel while Go-to does; the news waits.
    assert "No visible hyperlinks." in panel_says(page)
    assert "Agent replied" not in panel_says(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(".lf-live")).to_have_text(
        "No hint d. The current hints are unchanged."
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    resized(page, 1200, 800)
    expect_panel_says(page, "No visible hyperlinks.")
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS).first).to_be_visible()
    expect(page.locator(".lf-live")).to_have_text("All go-to targets.")
    page.wait_for_timeout(100)
    assert (
        page.evaluate(
            "() => window.__liveChanges.filter(words => "
            "words === 'Agent replied — open Threads').length"
        )
        == 1
    ), "showing deferred news announced it a second time"

    # The obligation route may scroll these hyperlinks out of the visible target map.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("h")
    links = page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')
    expect(links).to_have_count(3)
    expect(page.locator(f'{CHIPS}:not([data-lf-go-to-kind="Link"])')).to_have_count(0)
    resized(page, 1180, 800)
    expect(links).to_have_count(3)
    expect(page.locator(f'{CHIPS}:not([data-lf-go-to-kind="Link"])')).to_have_count(0)
    page.keyboard.type(address_code(page, "Link", "lk2"))
    page.wait_for_url(re.compile(r"#p2$"))
    expect(page.locator("#p2")).to_be_focused()


@pytest.mark.shifts_unsurveyed
def test_the_g_chord_reaches_named_surfaces_and_visible_targets(browser, serve):
    """Mnemonics reach global surfaces; generated hints reach the visible scene.

    The panel's Threads and On me, the Page Map dialog, and page edges keep stable
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
        page.locator(".lf-command-reference [role=row][data-lf-command]").evaluate_all(
            "rows => rows.map(row => row.dataset.lfCommand)"
        )
    )
    alignment = page.locator(
        '.lf-command-reference [role=row][data-lf-command="reading.align.top"]'
    )
    expect(alignment).to_have_count(1)
    # Alignment has a page-level route even when no reading item stands while
    # the reference opens from chrome.
    expect(alignment.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "z"])
    overlaps = goto.locator("[role=row][data-lf-command]").evaluate_all(
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
    expect(page.locator(".lf-live")).to_contain_text("type a hint")

    # A panel mnemonic completes the sequence and leaves the user in that view of the
    # panel, where its own scoped keys are immediately available.
    threads = page.locator(panel_view("threads"))
    page.keyboard.press("Shift+t")
    expect(threads).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # The On me sequence follows the same contract: open the view, whose walk's first
    # step lands on its first card.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    expect(page.locator(panel_view("queue"))).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("ArrowDown")
    expect(page.locator(".lf-fp-on-item").first).to_be_focused()

    # Replacing one view with another is lateral: Threads replaces On me while it
    # stands, and the Escape out of Threads lands on the page rather than putting On me
    # back.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # Page Map stands over whatever the user already had, so closing it leaves On me
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
            "searchbox", name="Find an action, status, or location in Page Map"
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
    expect(page.locator(PANEL)).to_have_attribute("data-open", "queue")
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
            "searchbox", name="Find an action, status, or location in Page Map"
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
    expect(page.locator("details.lf-details")).to_have_count(0)
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
             const first = document.getElementById('dsc-head').getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.top + c.height / 2 - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary starts at"
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
    # register holds capabilities, and a control is a route to one — so before this the
    # only keyboard way to it was Tab. The arrival is the press, so the option is chosen.
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
    expect(page.locator("#opt-a")).to_have_attribute("chosen", "")

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
    expect(threads).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # Typing contexts are untouched: in a box, the whole sequence is text.
    page.keyboard.press("c")
    box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    expect(box).to_be_focused()
    page.keyboard.type("gc1")
    expect(box).to_have_js_property("value", "gc1")
    expect(box).to_be_focused()
