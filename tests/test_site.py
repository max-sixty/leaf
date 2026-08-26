"""The published site: what the build assembles, and what a reader gets.

The site is the repo's own pages plus every example as a live page, so most of what
could go wrong is a path that meant one thing in a checkout and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

A page under /examples has to be reached over HTTP: its markup names /theme.css and
/leaf.js at a server root, and Chrome refuses an ES module from a file:// origin
besides. The docs pages are read as files, which is how a checkout reads them.
"""

import importlib.util
import json
import re
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import expect

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/CLAUDE.md, "A wait consumes a fact the system states".
from render_support import BOTH_STAMPS, navigate, open_page, select

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "plugins" / "leaf" / "skills" / "leaf" / "assets"
DEFAULT_PACKAGE = ROOT / "plugins" / "leaf" / "skills" / "leaf" / "packages" / "default"
COMMAND_HUB_PACKAGE = ROOT / "examples" / "packages" / "command-hub"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"

_spec = importlib.util.spec_from_file_location("site", ROOT / "scripts" / "site.py")
site_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site_build)

# The theme's paper, light and dark, as the browser reports a background.
PAPER = {"light": "rgb(250, 249, 245)", "dark": "rgb(25, 24, 21)"}
PHONE = {"width": 390, "height": 844}

# The module-scoped build and host are one shared setup, so they belong to one
# xdist work unit rather than being rebuilt independently on every worker.
pytestmark = [pytest.mark.nightly, pytest.mark.xdist_group(name="site")]


def pages_under(directory):
    """The pages a sweep walks, proved to exist before it walks them. Four of the
    checks below are loops over a glob and nothing else, so a directory that moved or
    was renamed turns every one of them into a sweep that pressed nothing — green, and
    for the wrong reason (tests/CLAUDE.md, "A sweep that walks controls by index must
    prove it pressed them")."""
    pages = sorted(directory.glob("*.html"))
    assert pages, f"no pages under {directory}"
    return pages


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """One build for the module: it vendors a layer and checks thirteen examples."""
    out = tmp_path_factory.mktemp("published") / "site"
    site_build.build(out)
    return out


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def hosted(site):
    """The site on a port, which is the only way an example's own links resolve."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(site)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def example_url(hosted, name):
    return f"{hosted}/examples/{name}/versions/v1.html"


def opened(page, errors, url):
    """A navigation this module makes for itself, waiting on what `open_page` waits
    on — the document's stamp and the log's — since a page at the first alone has a
    banner the reader would not recognize (tests/CLAUDE.md)."""
    navigate(page, errors, url, wait_until="load")


def test_the_pages_link_the_theme_the_site_serves(site):
    """One stylesheet on the site, and it is the one a page directory vendors: a docs
    page names both halves in a checkout because there is no merged file there to name,
    and linking both here would restate the default package over the top of itself."""
    for page in pages_under(DOCS):
        published = (site / page.name).read_text()
        assert published.count('href="theme.css"') == 1, page.name
        assert "packages/default/theme.css" not in published, (
            f"{page.name} still links the default theme beside the merged one"
        )
        for attribute in ('href="../', 'src="../'):
            assert attribute not in published, f"{page.name} kept a checkout path"
    served = (site / "theme.css").read_text()
    for source in (
        ASSETS / "theme.css",
        DEFAULT_PACKAGE / "theme.css",
        COMMAND_HUB_PACKAGE / "theme.css",
    ):
        assert source.read_text().rstrip() in served, (
            f"the theme the site serves is missing {source.parent.name}'s half"
        )


def test_only_the_stylesheet_link_becomes_the_served_copy(site):
    """packages.html links the theme twice — once as the page's stylesheet, once as
    source to read — and the two have to land in different places. Rewriting on the path
    alone sends a reader after the token block to the CSS the site serves, which is a
    resolving link the dead-link check has nothing to say about and the wrong file."""
    published = (site / "packages.html").read_text()
    source = f"{site_build.REPO}/blob/main/plugins/leaf/skills/leaf/assets/theme.css"
    assert f'href="{source}"' in published
    assert published.count('href="theme.css"') == 1


def test_the_site_serves_the_whole_layer_a_page_asks_for(site):
    """A page asks for its layer by absolute path, so the layer is the site's root. Any
    one of these missing is a page that opens unstyled, unupgraded, or not at all — and
    a static host reports none of it."""
    for name in ("theme.css", "registry.json", "icon.svg", "runtime.js", "leaf.js"):
        assert (site / name).is_file(), f"the site root has no {name}"
    generation = json.loads((site / "registry.json").read_text())["$layer"][
        "generation"
    ]
    source = (ASSETS / "leaf.js").read_text()
    assert source.count('"__LEAF_LAYER_GENERATION__"') == 1
    assert (site / "runtime.js").read_text() == source.replace(
        '"__LEAF_LAYER_GENERATION__"', json.dumps(generation)
    ), "the runtime the site serves is not the shipped file"
    for sub in ("runtime", "widgets", "vendor", "media"):
        assert list((site / sub).iterdir()), f"{sub}/ is empty at the site root"
    for source in pages_under(EXAMPLES):
        version = site / "examples" / source.stem / "versions" / "v1.html"
        assert version.read_text() == source.read_text(), (
            f"{source.name} was published as something other than the file in the tree"
        )
        assert "versions/v1.html" in (version.parent.parent / "index.html").read_text()


def test_a_link_that_reaches_nothing_stops_the_build(site, tmp_path):
    staged = tmp_path / "staged"
    shutil.copytree(site, staged)
    (staged / "index.html").write_text('<a href="whats-new.html">news</a>')

    with pytest.raises(SystemExit) as stopped:
        site_build.check_links(staged)
    assert "whats-new.html" in str(stopped.value)


def test_a_directory_link_with_no_index_stops_the_build(site, tmp_path):
    """What a host answers a directory with is its index, so that is what has to be
    there. An existence check passes on the directory itself and publishes a 404."""
    staged = tmp_path / "staged"
    shutil.copytree(site, staged)
    (staged / "examples" / "triage-board" / "index.html").unlink()

    with pytest.raises(SystemExit) as stopped:
        site_build.check_links(staged)
    assert "triage-board" in str(stopped.value)


def test_every_example_stands_as_a_live_page(site, hosted, browser):
    """The reader gets the page working rather than a picture of it.

    The banner is the proof: the runtime builds it after reading /api/state, so a page
    wearing one has the whole layer up and something answering the two paths behind it.
    The version it names is the second half — the runtime reads that number off the
    document's own path, so a page published anywhere else would say nothing there while
    looking otherwise perfect."""
    examples = pages_under(EXAMPLES)
    page, errors = open_page(browser, example_url(hosted, examples[0].stem))
    try:
        for source in examples:
            opened(page, errors, example_url(hosted, source.stem))
            expect(page.locator(".lf-banner .lf-version")).to_have_text("v1 ▾")
            expect(page.locator(".lf-status-text")).to_contain_text(
                "Nobody is behind this page"
            )
            assert not errors, f"{source.name}: {errors[:3]}"
    finally:
        page.close()


def test_the_banner_says_nobody_rather_than_claiming_a_watcher(site, hosted, browser):
    """A published example is waiting for nobody, and the banner has to say so in both
    of the things it says at once.

    The words were the easy half and the dot was the half that gave it away: the page
    reported itself as listening, since that was the only judged state the runtime would
    let a session speak its own detail in, and the seat drew the green of a live watcher
    with "The demo awaits" over it. Every word after the dash was then spent denying a
    claim only the dot had made. `unattended` is the state that had been missing, and the
    tone is the assertion that matters — a reader takes the colour in before the sentence,
    and it is the one part of a banner that cannot be softened by wording."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        expect(page.locator(".lf-banner .lf-status-text")).to_have_text(
            "Nobody is behind this page. What you do here stays in this browser."
        )
        # No tone at all — not the green of a watcher, nor the amber of one falling
        # behind. The banner's own dot: the leaves panel mirrors this page as a row, so
        # a bare .lf-dot would resolve to that copy too (the browser suite says the same).
        expect(page.locator(".lf-banner .lf-dot")).to_have_class(
            re.compile(r"^lf-dot\s*$")
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_every_example_says_what_it_is_and_links_back(site, hosted, browser):
    """The label the site puts at the head of a published example.

    A visitor arrives on a URL somebody sent them, and everything the page shows is the
    document and the runtime's chrome — neither of which says what this is or that the
    reply it invites reaches nobody. The banner carries the short form, the label the
    whole of it, and the label is the only way back to the site.

    Its links are the half the build cannot check: `check_links` reads the markup the
    build wrote, and these are written by a module, so a rename under `docs/` would send
    every example to a 404 with nothing anywhere to say so. The build's own resolver is
    what answers here, so a link in the label fails the way a link in a page does."""
    examples = pages_under(EXAMPLES)
    page, errors = open_page(browser, example_url(hosted, examples[0].stem))
    try:
        for source in examples:
            opened(page, errors, example_url(hosted, source.stem))
            label = page.locator("main > .sitenote")
            expect(label).to_contain_text("A live example of a leaf page.")
            expect(label).to_contain_text("nothing you do here leaves your own browser")
            published = site / "examples" / source.stem / "versions" / "v1.html"
            targets = label.locator("a").evaluate_all(
                "links => links.map(a => a.getAttribute('href'))"
            )
            # The count, so a label that came back with no links at all fails here
            # rather than sailing through the loop under it having checked nothing.
            assert len(targets) == 3, (
                f"{source.name}: the label has {len(targets)} links"
            )
            for target in targets:
                assert site_build.resolves(site, published, target.split("#")[0]), (
                    f"{source.name}: the label links {target}, which the site has not got"
                )
            assert not errors, f"{source.name}: {errors[:3]}"
    finally:
        page.close()


# The drag's own last step, waited out rather than timed: a timeout queued once the drag
# has returned runs behind the one the runtime queued from that mouseup, and one frame
# behind that is the key line as this drag left it. Why `expect` cannot ask instead is
# tests/CLAUDE.md, "A state the page passes through is not a state to poll for".
AFTER_THE_DRAG = """() => new Promise(done => setTimeout(() => requestAnimationFrame(
  () => done({ text: getSelection().toString(),
               says: document.querySelector('.lf-keyline').textContent }))))"""


def drag_across(page, selector):
    """Select an element's first line, and read what the page made of it."""
    box = page.locator(selector).first.bounding_box()
    select(
        page, (box["x"] + 4, box["y"] + 6), (box["x"] + box["width"] - 24, box["y"] + 6)
    )
    return page.evaluate(AFTER_THE_DRAG)


def test_the_label_is_chrome_rather_than_words_to_quote(site, hosted, browser):
    """The site's voice, so the comment loop must not offer it.

    The label stands inside <main>, where everything else is the page's own words and a
    drag raises the pill that opens a composer on them. What holds it out is the class
    the anchor pass reads as "not the document" — and losing that would be invisible
    until a reader had quoted the label into a comment, where the quote names text the
    published file has never held and resolves against nothing.

    What each drag amounted to is read off the key line, which names what `c` would
    comment on from the same anchor the button carries. Both readings are then a word
    the page says rather than an absence to hold a window open for — and the page's own
    lede goes first, since a line still naming the page after a drag that reached
    nothing is a refusal this would report as the label's."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        control = drag_across(page, "#decision-lede")
        assert "monolith split" in control["text"]
        assert "comment on the selection" in control["says"], (
            "the drag never reached the runtime"
        )

        label = drag_across(page, "main > .sitenote p")
        assert "live example" in label["text"]
        # The word `c` carries with nothing in hand — it goes to the comments rather
        # than opening a box on anything, and "comment on the selection" does not
        # contain it, so the two readings still tell each other apart.
        assert "comments" in label["says"], (
            "the site's own label was offered as a passage to quote"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_shipped_log_opens_its_example_on_its_thread(site, hosted, browser):
    """An example that ships a log beside it arrives mid-conversation here too.

    The thread is the one thing no markup describes, so a copy of the markup could never
    carry one however it was written — which is what put every published example's
    comment loop out of reach until the pages went live. The session reads the log the
    build laid beside the versions before the runtime asks for it, so the panel is right
    on the first paint rather than filling in under a reader already reading it.

    The anchor is the half that rots quietly: the quote is captured against the file, and
    a rewritten sentence leaves it resolving to nothing and the thread standing detached,
    with no error anywhere."""
    page, errors = open_page(browser, example_url(hosted, "ship-review"))
    try:
        expect(page.locator(".lf-comments")).to_have_text("Comments (1)")
        page.locator(".lf-comments").click()
        thread = page.locator(".lf-panel .lf-thread").first
        expect(thread).to_contain_text("One reconnect in forty is worse")
        expect(thread.locator("blockquote")).to_have_text("“One reconnect in about 40”")
        assert page.locator(".lf-panel .lf-quote.detached").count() == 0, (
            "the shipped anchor found nothing on the page it was captured from"
        )
        # Painted, not merely resolved: the mark is what puts the reader at the passage.
        assert "lf-mark" in page.evaluate("() => [...CSS.highlights.keys()]")
        # And the question Claude asks in that thread is a widget, which reaches
        # this page the one way a static host can carry one: docs/session.js puts
        # the log in the reader's own tab, so nothing here upgraded it from a
        # served log. A reader can answer it where they are standing.
        ask = page.locator("#off-slip")
        expect(ask).to_be_visible()
        assert ask.locator("[data-lf-offer]").count() > 0, (
            "the group renders on the site with nothing to press, so the ask "
            "is a picture of one"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_shipped_data_snapshot_opens_in_its_package_projection(site, hosted, browser):
    """The static session delivers package data through the live state contract."""
    stored = json.loads((site / "examples" / "command-hub" / "data.json").read_text())
    assert (
        stored["sources"]["atlas-worktrees"]["value"]["tree-w-1"]["branch"]
        == "atlas/xml-declarations"
    )

    page, errors = open_page(browser, example_url(hosted, "command-hub"))
    try:
        snapshot = page.locator('#tree-w-1 [data-lf-datum="tree-w-1"]')
        expect(snapshot).to_have_count(1)
        expect(snapshot).to_contain_text("atlas/xml-declarations")
        expect(snapshot).to_contain_text("tests running")
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_comment_lands_in_the_thread_with_its_quote(site, hosted, browser):
    """The whole loop a static host could not hold before: the reader selects a passage,
    the comment goes into a log, the page renders it back with the passage quoted, and
    the one thing missing — an agent — says so in the thread rather than leaving the
    reader's words in a box that ate them."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        # What the page opens with, since an example that ships a log opens with
        # threads already counted. The claim here is that the reader's own comment
        # adds one, which is a claim about the gesture rather than about the corpus.
        opened_with = page.locator(".lf-panel .lf-thread").count()
        box = page.locator("#decision-lede").bounding_box()
        select(
            page,
            (box["x"] + 4, box["y"] + 8),
            (box["x"] + box["width"] - 40, box["y"] + box["height"] - 8),
        )
        # The pill a selection raises, which is how a reader reaches the composer.
        page.locator(".lf-fab").click()
        page.locator(".lf-composer textarea").fill("Does this cover key rotation?")
        page.locator(".lf-composer .lf-btn.primary").click()

        # The thread holding the words just written, rather than whichever is first:
        # an example that ships a log opens with threads already in the panel, and
        # theirs would be first. design-decision ships none today, so `.first` was
        # right by accident and would stop being on the day it does.
        thread = page.locator(
            ".lf-panel .lf-thread", has_text="Does this cover key rotation?"
        )
        expect(thread).to_contain_text("Does this cover key rotation?")
        expect(thread.locator("blockquote")).to_contain_text("session state homeless")
        expect(page.locator(".lf-comments")).to_have_text(
            f"Comments ({opened_with + 1})"
        )
        # The demo answers once, in its own name, and says what the page can't do.
        expect(thread).to_contain_text("This is the demo answering, not an agent")
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_decision_holds_across_a_reload(site, hosted, browser):
    """The log is the state here as much as anywhere: a pick is an action, and what puts
    it back on the next load is replay rather than anything the markup remembers."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        chosen = (
            "() => [...document.querySelectorAll('lf-option[chosen]')].map(o => o.id)"
        )
        page.locator("#opt-jwt .lf-pick").click()
        expect(page.locator("#session-options")).to_have_attribute(
            "data-lf-pending", "1"
        )
        assert "opt-jwt" in page.evaluate(chosen)

        page.reload(wait_until="load")
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator("#session-options")).to_have_attribute(
            "data-lf-pending", "1"
        )
        assert "opt-jwt" in page.evaluate(chosen), "the reload lost the reader's pick"
        assert not errors, errors[:3]
    finally:
        page.close()


def test_what_a_reader_leaves_on_one_page_stays_on_it(site, hosted, browser):
    """One origin serves every example here, where a server serves one page — so both
    stores keyed by nothing but the browser's own carry from one example to the next.
    The log is one: a comment written on a decision page would be waiting on a ship
    review. The reading position is the other, and it is the worse of the two, because
    an offset means something on both pages and lands the reader mid-document on one
    they have never opened."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        page.locator(".lf-comments").click()  # the box lives in the panel
        page.locator(".lf-general textarea").fill("Where does this go?")
        page.locator(".lf-general .lf-btn.primary").click()
        expect(page.locator(".lf-comments")).to_have_text("Comments (1)")
        # The page's own scroller (the runtime's `pageScroller`), moved the way a
        # reader moves it far enough down that the landmark is worth restoring.
        page.evaluate("() => document.body.scrollTo({top: 1500, behavior: 'instant'})")
        assert page.evaluate("() => document.body.scrollTop") > 0, (
            "the document did not scroll, so the landmark under test was never written"
        )

        # An example that ships no log of its own, so the count there is the reader's
        # own doing or nobody's. Asked of the corpus rather than named, since a page
        # that gains a companion log would otherwise turn this into a test of the seed.
        plain = next(
            p.stem
            for p in pages_under(EXAMPLES)
            if not p.with_suffix(".jsonl").exists()
        )
        opened(page, errors, example_url(hosted, plain))
        expect(page.locator(".lf-comments")).to_have_text("Comments (0)")
        assert page.evaluate("() => document.body.scrollTop") == 0, (
            "the ship review opened at the offset the reader left on another page"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_site_takes_its_palette_from_the_theme(site, browser, scheme):
    page = browser.new_page(color_scheme=scheme)
    try:
        for name in (p.name for p in pages_under(DOCS)):
            page.goto((site / name).as_uri())
            assert (
                page.evaluate("getComputedStyle(document.body).backgroundColor")
                == (PAPER[scheme])
            ), name
    finally:
        page.close()


def test_the_pages_fit_a_phone(site, browser):
    """Nothing scrolls sideways at 390px — the nav wraps, the screenshots scale,
    and a command too long for the column scrolls inside its own block.

    The site's own pages, not the examples it publishes: a page with a suggestion
    on it hangs the accept/reject controls in the margin, and at 390px
    there is no margin to hang them in. That is the live page's question rather
    than the site's, and it is not answered here."""
    page = browser.new_page(viewport=PHONE)
    try:
        for name in (p.name for p in pages_under(DOCS)):
            page.goto((site / name).as_uri())
            overflow = page.evaluate(
                "() => { const b = document.body;"
                " return b.scrollWidth - b.clientWidth; }"
            )
            assert overflow <= 0, f"{name} scrolls {overflow}px sideways on a phone"
    finally:
        page.close()
