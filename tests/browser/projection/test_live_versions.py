"""How the live page adopts, stamps, reloads or refuses an arriving version, and which
URL follows which version."""

import re

import pytest
from click.testing import CliRunner
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    executable_revision,
    live_url,
)
from render_harness import (
    PANEL,
    RELEASE_FOCUS,
    expect_panel_says,
    holding,
    is_problem,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_control,
    panel_menu,
    refuse,
    sending,
    take_browser_errors,
    told,
    write,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_live_page_adopts_a_revision_and_stamps_it_without_replacing_main(
    browser, serve
):
    """A valid save advances the live surface; stamping only changes its label.

    Nothing here is executable, so the user keeps this document: the next file is
    fetched while they read, then its authored markup is patched onto the page they
    are reading. The URL, runtime identity, open chrome, `main` itself, and the
    passage's viewport coordinate therefore survive. Five paragraphs arrive above that
    passage so a raw scroll offset cannot satisfy the position assertion.
    """
    first = LIVE_V1.replace("<body>", '<body tabindex="0">')
    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    assert "/versions/" not in page.url, f"the live address redirected to {page.url}"

    page.locator("#live-reading").scroll_into_view_if_needed()
    page.evaluate(
        """() => { document.scrollingElement.scrollBy({
          top: document.getElementById('live-reading').getBoundingClientRect().top - 140,
          behavior: 'instant'
        }); window.__leafDocument = 'the same runtime';
          window.__leafMain = document.querySelector('main'); }"""
    )
    original_document = page.evaluate("performance.timeOrigin")
    before = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    open_threads(page)

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")

    assert page.evaluate("performance.timeOrigin") == original_document, (
        "the revision replaced the browser document rather than its authored page"
    )
    assert page.evaluate("window.__leafDocument") == "the same runtime", (
        "the revision replaced the browser document rather than its authored page"
    )
    assert page.evaluate("window.__leafMain === document.querySelector('main')"), (
        "the revision replaced the authored main rather than patching it"
    )
    assert "/versions/" not in page.url, (
        f"the update changed the live address to {page.url}"
    )
    expect(page.locator(PANEL)).to_have_attribute("data-open", "threads")
    after = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(after - before) <= 4, (
        f"the passage moved from {before}px to {after}px in the viewport"
    )
    expect(panel_control(page, "versions").locator(".lf-fp-value")).to_have_text(
        "Draft"
    )
    versions = panel_menu(page, "versions")
    expect(versions.locator(".lf-fp-version[data-current]")).to_contain_text(
        "Current · Draft after v1"
    )
    page.keyboard.press("Escape")
    assert page.locator('meta[name="description"]').get_attribute("content") == "second"
    assert page.locator("html").get_attribute("lang") == "fr"
    assert page.locator("html").get_attribute("data-live-root") == "second"
    expect(page.locator("html")).to_have_attribute("data-lf-live", "")
    expect(page.locator("html")).to_have_attribute("data-lf-interactive", "")
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

    # The revision owns authored body attributes, and the runtime's let-go still takes
    # the user off an element after the replacement.
    page.locator("#live-reading").evaluate(
        "el => { el.tabIndex = -1; el.focus({preventScroll: true}); }"
    )
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate("document.activeElement === document.body")

    page.evaluate("window.__leafMain = document.querySelector('main')")
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(serve.page_dir), "--text", "new findings"],
    )
    assert stamped.exit_code == 0, stamped.output
    told(page)
    expect(panel_control(page, "versions").locator(".lf-fp-value")).to_have_text("v2")
    page.keyboard.press("Escape")
    assert page.evaluate("window.__leafMain === document.querySelector('main')"), (
        "stamping the displayed revision replaced its main"
    )

    write(page_comment(page), "This comment belongs to the live draft.")
    with sending(page, "the comment on the live draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert events_model.read_events(serve.page_dir)[-1]["revision"] == 2


def test_a_stamped_live_draft_and_its_unstamped_view_keep_distinct_menu_rows(
    browser, serve
):
    """A newer held draft leaves two destinations on the prior revision."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(serve.page_dir), "--text", "second"],
    )
    assert stamped.exit_code == 0, stamped.output
    told(page)

    # The hold has to outlast every press this test makes through it, and it takes both
    # of the following to get there. A composer the user opened is one of the gestures
    # a revision install defers to and does not end when focus moves; words in a box the
    # user merely has focus in do, and the draft store rather than a hold is what
    # carries those across the install (`browser/AGENTS.md`, "Runtime
    # ownership").
    page.locator("#live-reading").click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Keep reading this revision.")
    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    # The fourth row is the one the third revision brings, so wait on the news that
    # revision lights rather than on the title, which already said this before the write
    # and so states no ordering at all.
    expect(page).to_have_title("Live second")

    # The leaf's menu is reached by keys, since a mouse press anywhere outside the
    # composer stands the composer down (standDown) — so reaching Versions by mouse
    # would end the hold on the very gesture that opens the menu, and whether the page
    # had followed by then would come down to whether a state read landed between the
    # two presses. The keyboard route leaves the composer open through both.
    page.locator(".lf-fp-leaf").press("Enter")
    expect(page.locator(PANEL)).to_have_attribute("data-menu", "")
    page.locator('.lf-fp-item[data-row="versions"]').press("Enter")
    rows = page.locator(".lf-fp-menu[data-level=versions] .lf-fp-version")
    # The third revision's row is what the hold leaves the page short of.
    expect(rows).to_have_count(4)
    latest = rows.filter(has_text="Current · Draft after v2").locator(".lf-fp-item")
    stamped_row = rows.filter(has_text=re.compile(r"^\s*v2\b")).locator(".lf-fp-item")
    draft_row = rows.filter(has_text="This view · v2").locator(".lf-fp-item")
    expect(stamped_row).to_have_count(1)
    expect(draft_row).to_have_count(1)

    latest.press("Enter")
    expect(page).to_have_title("Live third")
    panel_menu(page, "versions")
    expect(rows).to_have_count(3)
    # The menu draws its rows afresh at each opening: the stamped version keeps its
    # row, and the view of its revision the page has left has none.
    expect(stamped_row).to_have_count(1)
    expect(draft_row).to_have_count(0)
    stamped_row.click()
    page.wait_for_url(re.compile(r"/versions/v2\.html\?pin=$"))


def test_a_live_revision_with_new_authored_code_reloads_the_document(browser, serve):
    """A new constructor and its listeners run once, with fresh local state. The
    browser here has no view transition API, since fresh-document activation does not
    depend on same-document animation; the other fresh-document journeys keep it."""
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() {
    let count = 0;
    const button = document.createElement('button');
    const label = () => { button.textContent = `Count ${count}`; };
    button.addEventListener('click', () => { count += 1; label(); });
    label();
    this.append(button);
  }
});
document.querySelector('#counter').append(document.createElement('page-counter'));
</script>"""
    first = LIVE_V1.replace("</head>", module + "</head>").replace(
        "</main>", '<div id="counter"></div></main>'
    )
    second = LIVE_V2.replace(
        "</head>", module.replace("count += 1", "count += 10") + "</head>"
    ).replace("</main>", '<div id="counter"></div></main>')
    page = open_page(browser, live_url(serve(first)))
    page.get_by_role("button", name="Count 0", exact=True).click()
    expect(page.get_by_role("button", name="Count 1", exact=True)).to_be_visible()
    original_document = page.evaluate("performance.timeOrigin")
    page.evaluate("document.startViewTransition = undefined")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live second")
    page.get_by_role("button", name="Count 0", exact=True).click()
    expect(page.get_by_role("button", name="Count 10", exact=True)).to_be_visible()
    assert page.evaluate("performance.timeOrigin") != original_document
    assert "/versions/" not in page.url
    assert "_leaf-revision" not in page.url


def test_a_stamped_url_stays_pinned_while_the_live_root_follows_a_draft(browser, serve):
    version_url = serve(LIVE_V1)
    pinned = open_page(browser, version_url)
    live = open_page(browser, live_url(version_url))

    (serve.page_dir / "index.html").write_text(LIVE_V2.replace("</main>", ""))
    told(live)
    told(pinned)
    # The failed save is a held error, which the empty field says in its status's place.
    expect_panel_says(live, "Latest edit not shown")
    expect_panel_says(pinned, "Latest edit not shown", says=False)
    expect(live).to_have_title("Live first")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(live)
    told(pinned)

    expect(live).to_have_title("Live second")
    expect_panel_says(live, "Latest edit not shown", says=False)
    expect(panel_control(live, "versions").locator(".lf-fp-value")).to_have_text(
        "Draft"
    )
    expect(
        panel_menu(live, "versions").locator(".lf-fp-version[data-current]")
    ).to_contain_text("Current · Draft after v1")
    expect(pinned).to_have_title("Live first")
    expect(pinned).to_have_url(re.compile(r"/versions/v1\.html"))
    expect(panel_control(pinned, "versions").locator(".lf-fp-value")).to_have_text("v1")


def test_the_live_page_retains_a_page_comment_while_adopting_revisions(browser, serve):
    """A page comment editor belongs to runtime chrome, so an authored patch can
    arrive while it holds unsent words. The draft and focus survive each revision."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))
    general = page_comment(page)
    write(general, "Do not replace the page under these words.")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")
    expect(general).to_be_focused()
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )

    # Leaving the text box preserves its durable draft on the live address.
    page.keyboard.press("Escape")
    expect(general).not_to_be_focused()
    assert "/versions/" not in page.url
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )

    # Continue editing after the first release, then adopt v3 while the field stands.
    page_comment(page)
    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    expect(page).to_have_title("Live third")
    expect(general).to_be_focused()
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )

    write(general, "")
    page.locator("#live-reading").click()
    told(page)
    expect(page).to_have_title("Live third")
    assert "/versions/" not in page.url
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blive-second\b"))
    assert page.locator("body").get_attribute("data-live-body") is None
    assert (
        page.locator("body").evaluate(
            "el => el.style.getPropertyValue('--live-body').trim()"
        )
        == ""
    ), "the retired version's authored inline property survived"
    assert page.locator('meta[name="description"]').get_attribute("content") == "third"


def test_a_pending_navigation_prevents_another_live_activation(browser, serve):
    """The departing document stops applying state after its navigation starts.

    Each revision changes the page's own code, so each is followed into a fresh
    document and there is a navigation to hold.
    """
    page = open_page(browser, live_url(serve(executable_revision(LIVE_V1, "one"))))
    held = []

    def hold_navigation(route):
        if route.request.is_navigation_request():
            held.append(route)
        else:
            route.continue_()

    page.route("**/*", hold_navigation)
    try:
        (serve.page_dir / "index.html").write_text(executable_revision(LIVE_V2, "two"))
        holding(page, held, 1, "the fresh revision document")
        # A newer save overtakes this navigation. The same live root response owns
        # the final revision; the old realm cannot launch another activation.
        (serve.page_dir / "index.html").write_text(
            executable_revision(LIVE_V3, "three")
        )
        held[0].continue_()
        told(page)
        expect(page).to_have_title("Live third")
        assert len(held) == 1
    finally:
        page.unroute("**/*", hold_navigation)


def test_a_revision_the_page_has_to_refuse_leaves_the_beat_beating(browser, serve):
    """A refusal is an answer the beat has to be able to read.

    A page can adopt a newer revision without installing it. The fetch for its document
    can fail, which is reported and left for the version chip to retry, so the user
    stands on the older revision with the newer one named in the state the page applied.
    Every beat from then on asks the same preparation whether it would activate now. When
    a later fetch answers from a layer re-vendored under the page, the preparation refuses
    instead: this page is already reloading, and the revision belongs to the layer it is
    leaving. An answer only the install path knew how to read made the beat's question
    throw, and the beat carries the clock, the deferred corrections, and this retry, so a
    refusal stopped all three and reported a page failure on the way out of a document
    nobody had complained about. A re-vendor rewrites the whole page directory, so the
    registry the page probes names the new generation as well; that is what tells the
    page a reload has a different document to land on.
    """
    first = leaf_page(
        "Beat first",
        '<h1 id="bt-title">Beat</h1>\n<p id="bt-line">The cutover has not started.</p>',
    )
    second = first.replace("Beat first", "Beat second").replace(
        "The cutover has not started.", "The cutover finished."
    )
    page = open_page(browser, live_url(serve(first)))
    asked = []
    # The state applies the first refusal and adopts the revision anyway; the two after
    # it are beats, which is what puts the beat on the answer the fourth ask brings back.
    REFUSALS = 3

    def answer(route):
        asked.append(route)
        if len(asked) <= REFUSALS:
            refuse(route)
            return
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Layer": "re-vendored"},
        )

    # The page probes its own source before reloading, because only a source that has
    # moved has another document to give. A re-vendor moves the whole page directory, so
    # that one probe answers for the new generation; the document it brings back is the
    # re-vendored page, which this fixture leaves as the directory it really is.
    probes = []

    def revendored(route):
        probes.append(route)
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={
                **response.headers,
                **({"Leaf-Layer": "re-vendored"} if len(probes) == 1 else {}),
            },
        )

    page.route("**/revisions/*", answer)
    try:
        (serve.page_dir / "index.html").write_text(second)
        page.route("**/registry.json", revendored)
        holding(page, asked, REFUSALS + 1, "the asks the beats made for the revision")
        # The refusal reloads, and the page that comes back is on the layer it was told
        # about, holding the revision it could not be given in place.
        expect(page).to_have_title(
            "Beat second", timeout=render_checks_model.HANDOVER_DEADLINE_MS
        )
        wait_until_ready(page)
        problems = take_browser_errors(page)
        assert len(problems) >= 2 and all(
            is_problem(p, "failed to load") for p in problems
        ), (
            "the beats did not come through with only their own refused asks behind "
            f"them: {problems}"
        )
    finally:
        page.unroute("**/revisions/*", answer)
        page.unroute("**/registry.json", revendored)
