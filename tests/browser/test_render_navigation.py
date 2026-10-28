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
    """A fixed card cannot reveal itself by scrolling its already-visible passage away."""
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
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    scroll_settled(page)
    expect(thread).to_be_in_viewport(ratio=1)
    page.keyboard.press("c")
    reply = page.get_by_role("textbox", name="Reply", exact=True)
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
    mark = external.locator(":scope > .lf-external-mark")

    expect(external).to_have_attribute("target", "_blank")
    expect(external).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source opens in a new tab")
    # The treatment stands inside the link, so the paragraph ends where it was written.
    expect(page.locator("#external ~ *")).to_have_count(0)
    expect(mark).to_be_visible()
    assert mark.evaluate("node => node.localName") == "svg"
    expect(mark.locator(":scope > path")).to_have_count(1)
    expect(mark).to_have_attribute("aria-hidden", "true")
    expect(page.locator("#fragment > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#fragment")).not_to_have_attribute("target", "_blank")
    expect(page.locator("#svg-external > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#svg-external")).not_to_have_attribute("target", "_blank")

    tab = opened_tab(page, destination, external.click)
    expect(tab).to_have_url(f"{other_url}/")
    expect(page).to_have_url(url.split("?", 1)[0])
