"""The published site: what the build assembles, and what a reader gets.

The site is the repo's own pages plus every example as a live page, so most of what
could go wrong is a path that meant one thing in a checkout and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP: product sources now name the same root layer and
module as the examples, so file:// is no longer a second supported document mode.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from example_data import example_versions
from interact_support import SHIPPED_PACKAGES
from leaf.event_log import _parse_events
from leaf.events import bare_reaction, build_threads
from leaf.passages import enclosing_ids
from playwright.sync_api import expect

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/CLAUDE.md, "A wait consumes a fact the system states".
from render_support import BOTH_STAMPS, ONE_FRAME, navigate, open_page, select, watched

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "skills" / "leaf" / "assets"
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


def example_title(stem: str) -> str:
    """The h1 an example's own source carries, so a retitled example cannot strand a
    test on its old words."""
    source = (EXAMPLES / f"{stem}.html").read_text(encoding="utf-8")
    return re.search(r"<h1>(.*?)</h1>", source, re.DOTALL).group(1).strip()


def authored_examples():
    """The public examples, with the one generated browser-stress fixture removed."""
    pages = pages_under(EXAMPLES)
    corpus = [page for page in pages if page.stem == "corpus"]
    authored = [page for page in pages if page.stem != "corpus"]
    assert len(corpus) == 1, f"expected one internal corpus, found {corpus}"
    assert authored, "excluding the corpus left no examples to publish"
    return authored


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """One build for the module: it vendors a layer and checks every example."""
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
    """The route a reader lands on: the example's newest published version."""
    newest = site_build.newest_version(EXAMPLES / f"{name}.html")
    return f"{hosted}/examples/{name}/versions/{newest}"


def product_url(hosted, name):
    """The canonical live-root route for one product source."""
    return hosted + site_build.PRODUCT_ROUTES[name]


def media_url(source: Path) -> str:
    """The content address `leaf page media` gives an authored image."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    return f"/media/{digest}{source.suffix.lower()}"


def opened(page, errors, url):
    """A navigation this module makes for itself, waiting on what `open_page` waits
    on — the document's stamp and the log's — since a page at the first alone has a
    banner the reader would not recognize (tests/CLAUDE.md)."""
    navigate(page, errors, url, wait_until="load")


def test_the_pages_link_the_theme_the_site_serves(site):
    """Every product document asks for the one composed root stylesheet."""
    for page in pages_under(DOCS):
        target = site_build.product_target(site, site_build.PRODUCT_ROUTES[page.name])
        published = target.read_text()
        assert published.count('href="/theme.css"') == 1, page.name
        for attribute in ('href="../', 'src="../'):
            assert attribute not in published, f"{page.name} kept a checkout path"
    served = (site / "theme.css").read_text()
    # Every half the site's own layer composes, read off examples/layer.json rather
    # than listed, so a package added there is covered without a second edit here.
    halves = [
        *(root / "theme.css" for root in SHIPPED_PACKAGES),
        DOCS / "package" / "theme.css",
    ]
    missing = [source.parent.name for source in halves if not source.is_file()]
    assert missing == [], f"shipped roots without a theme half: {missing}"
    for source in halves:
        assert source.read_text().rstrip() in served, (
            f"the theme the site serves is missing {source.parent.name}'s half"
        )


def test_product_pages_are_published_without_a_rewrite_dialect(site):
    sources = pages_under(DOCS)
    assert {source.name for source in sources} == set(site_build.PRODUCT_ROUTES)
    for source in sources:
        target = site_build.product_target(site, site_build.PRODUCT_ROUTES[source.name])
        assert target.read_bytes() == source.read_bytes(), source.name


def test_the_site_serves_the_whole_layer_a_page_decisions_for(site):
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
    site_idioms = json.loads((DOCS / "package" / "registry.json").read_text())[
        "$idioms"
    ]
    registry = json.loads((site / "registry.json").read_text())["$idioms"]
    assert set(site_idioms) <= set(registry)
    for source in authored_examples():
        # Every authored version is published, so the chooser on the static page has
        # somewhere to travel; the index forwards to the newest of them.
        for number, authored in enumerate(example_versions(source), start=1):
            version = site / "examples" / source.stem / "versions" / f"v{number}.html"
            assert version.read_text() == authored.read_text(), (
                f"{authored.name} changed while it was published"
            )
        newest = site_build.newest_version(source)
        index = site / "examples" / source.stem / "index.html"
        assert f"versions/{newest}" in index.read_text()


def test_every_product_route_is_a_live_leaf(site, hosted, browser):
    """Each authored product page reaches the real runtime as an independent draft."""
    names = list(site_build.PRODUCT_ROUTES)
    page, errors = open_page(browser, product_url(hosted, names[0]))
    try:
        for name in names:
            opened(page, errors, product_url(hosted, name))
            expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
            expect(page.locator(".lf-banner .lf-version")).to_have_text("Draft ▾")
            expect(page.locator(".lf-status-text")).to_contain_text(
                "Nobody is behind this page"
            )
            expect(page.locator("main > .sitenote")).to_have_count(0)
            state = page.evaluate("() => fetch('/api/state').then(r => r.json())")
            assert state["active"] == {
                "revision": 1,
                "version": None,
                "url": site_build.PRODUCT_ROUTES[name],
                "label": "Draft",
                "activated_at": None,
            }
            assert state["versions"] == []
            assert not errors, f"{name}: {errors[:3]}"
    finally:
        page.close()


def test_the_product_diagram_fits_without_its_own_scroll(hosted, browser):
    """The architecture is one sequence, so the diagram must fit its content box."""
    page, errors = open_page(browser, product_url(hosted, "how-it-works.html"))
    try:
        page.set_viewport_size({"width": 1200, "height": 900})
        diagram = page.locator("#arch")
        expect(diagram).to_be_visible()
        width = diagram.evaluate(
            "element => ({client: element.clientWidth, scroll: element.scrollWidth})"
        )
        assert width["scroll"] == width["client"]
        assert not errors, errors[:3]
    finally:
        page.close()


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


def test_an_invalid_product_document_stops_the_build(tmp_path, monkeypatch):
    """The builder crosses Leaf's gate rather than copying a plausible HTML shell."""
    staged_docs = tmp_path / "docs"
    shutil.copytree(DOCS, staged_docs)
    tour = staged_docs / "index.html"
    tour.write_text(
        tour.read_text().replace('<script type="module" src="/leaf.js"></script>', "")
    )
    monkeypatch.setattr(site_build, "DOCS", staged_docs)

    with pytest.raises(SystemExit) as stopped:
        site_build.build(tmp_path / "invalid-site", verify_links=False)
    assert "expected exactly one external <script src> tag, found 0" in str(
        stopped.value
    )


def test_the_public_catalog_is_a_visual_index_of_full_page_routes(
    site, hosted, browser
):
    """Every authored example appears once as a real preview and a standalone route.

    The absence checks are held by positive populations: catalog entries, loaded
    images, and the independently derived authored files. A vanished catalog
    cannot pass merely because it also contains no iframe or tab widget.
    """
    expected = {source.stem for source in authored_examples()}
    assert {path.name for path in DOCS.glob("example-*.jpg")} == {
        f"example-{stem}.jpg" for stem in expected
    }

    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(f"{hosted}/examples/", wait_until="load")
        page.wait_for_function(BOTH_STAMPS)
        entries = page.locator(".example-catalog > li .example-link")
        assert entries.count() == len(expected)
        pairs = entries.evaluate_all(
            "links => links.map(link => ({"
            " href: link.getAttribute('href'),"
            " image: link.querySelector('img').getAttribute('src'),"
            "}))"
        )
        reached = set()
        for pair in pairs:
            match = re.fullmatch(r"/examples/([a-z0-9-]+)/", pair["href"])
            assert match, pair
            stem = match.group(1)
            assert pair["image"] == media_url(DOCS / f"example-{stem}.jpg")
            reached.add(stem)
        assert reached == expected

        images = entries.locator("img")
        assert images.count() == len(expected)
        for index in range(images.count()):
            image = images.nth(index)
            image.scroll_into_view_if_needed()
            expect(image).to_be_visible()
            assert image.evaluate("img => [img.naturalWidth, img.naturalHeight]") == [
                896,
                560,
            ]

        assert page.locator("iframe, lf-tabs").count() == 0
        published = {
            path.name for path in (site / "examples").iterdir() if path.is_dir()
        }
        assert published == expected
        assert not errors, errors[:3]
    finally:
        page.close()


def test_every_example_stands_as_a_live_page(site, hosted, browser):
    """The reader gets the page working rather than a picture of it.

    The banner is the proof: the runtime builds it after reading /api/state, so a page
    wearing one has the whole layer up and something answering the two paths behind it.
    The version it names is the second half — the runtime reads that number off the
    document's own path, so a page published anywhere else would say nothing there while
    looking otherwise perfect."""
    examples = authored_examples()
    page, errors = open_page(browser, example_url(hosted, examples[0].stem))
    try:
        for source in examples:
            opened(page, errors, example_url(hosted, source.stem))
            newest = len(example_versions(source))
            expect(page.locator(".lf-banner .lf-version")).to_have_text(f"v{newest} ▾")
            expect(page.locator(".lf-status-text")).to_contain_text(
                "Nobody is behind this page"
            )
            assert not errors, f"{source.name}: {errors[:3]}"
    finally:
        page.close()


def test_an_example_paints_while_every_stage_of_site_startup_is_held(
    site, hosted, browser
):
    """The static showcase paints before JavaScript or its session is ready.

    Holding /leaf.js proves widget upgrade cannot be what made the document visible.
    The waiting pseudo-element's computed content proves the loading sheet does not
    exist, without waiting for an animation threshold. Once JavaScript starts, holding
    both seed files proves the runtime graph overlaps their reads. The data-bound diff
    remains empty while its captured source is held, then renders before presentation
    completes once that source arrives.
    """
    boot = []
    seeds = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/leaf.js", lambda route: boot.append(route))
    page.route("**/data.json", lambda route: seeds.append(route))
    page.route("**/events.jsonl", lambda route: seeds.append(route))

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(example_url(hosted, "pr-walkthrough"), wait_until="commit")
        expect(page.locator("h1")).to_have_text(example_title("pr-walkthrough"))
        expect(page.locator("h1")).to_be_visible()

        assert boot, "the positive control did not hold the site boot module"
        expect(page.locator("body > main")).to_have_css("pointer-events", "auto")
        assert (
            page.evaluate("() => getComputedStyle(document.body, '::after').content")
            == "none"
        ), "the waiting sheet painted before the site boot module arrived"

        with page.expect_request("**/runtime.js"):
            boot.pop().continue_()

        assert len(seeds) == 2, "both session seed requests were not still in flight"
        assert page.locator("body").get_attribute("data-lf-presented") is None
        expect(page.locator("#pr-exact-patch")).not_to_have_class(
            re.compile(r"\blf-rendered\b")
        )
        expect(page.locator("#pr-exact-patch details")).to_have_count(0)
        page.evaluate(
            """() => {
              const body = document.body;
              const diff = document.querySelector('#pr-exact-patch');
              window.__lfDataStampSawRendered = null;
              window.__lfPresentationSawRendered = null;
              new MutationObserver(records => {
                for (const record of records) {
                  if (record.target !== body) continue;
                  if (record.attributeName === 'data-lf-data-revision')
                    window.__lfDataStampSawRendered = diff.classList.contains('lf-rendered');
                  if (record.attributeName === 'data-lf-presented')
                    window.__lfPresentationSawRendered = diff.classList.contains('lf-rendered');
                }
              }).observe(body, {attributes: true});
            }"""
        )

        for route in seeds:
            route.continue_()
        seeds.clear()
        page.wait_for_load_state("load")
        expect(page.locator("#pr-exact-patch")).to_have_class(
            re.compile(r"\blf-rendered\b")
        )
        expect(page.locator("#pr-exact-patch details").first).to_be_visible()
        page.wait_for_function(BOTH_STAMPS)
        assert page.evaluate(
            "() => window.__lfDataStampSawRendered === true && "
            "window.__lfPresentationSawRendered === true"
        ), "the data/presentation readiness stamp preceded the bound diff render"
        assert errors == []
    finally:
        if boot:
            # If /leaf.js never started, do not let releasing it create new held seed
            # requests after the cleanup snapshot below.
            page.unroute("**/data.json")
            page.unroute("**/events.jsonl")
        for route in boot:
            route.continue_()
        for route in seeds:
            route.continue_()
        page.unroute_all(behavior="wait")
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
    examples = authored_examples()
    page, errors = open_page(browser, example_url(hosted, examples[0].stem))
    try:
        for source in examples:
            opened(page, errors, example_url(hosted, source.stem))
            label = page.locator("main > .sitenote")
            expect(label).to_contain_text("An example of a leaf page.")
            expect(label).to_contain_text("nothing you do here leaves your own browser")
            published = (
                site
                / "examples"
                / source.stem
                / "versions"
                / site_build.newest_version(source)
            )
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
# tests/CLAUDE.md, "A state the page passes through is not a state to poll for". The
# timeout bounds the queue hop only, so the frame is asked for through `ONE_FRAME`, which
# carries the deadline a bare `requestAnimationFrame` has not got.
AFTER_THE_DRAG = f"""async () => {{
  await new Promise(done => setTimeout(done));
  await ({ONE_FRAME})();
  const field = document.querySelector('.lf-fab-input');
  return {{ text: getSelection().toString(),
           quote: document.getElementById('lf-composer-quote')?.textContent ?? '',
           fieldOffered: Boolean(field?.checkVisibility()) }};
}}"""


def drag_across(page, selector):
    """Select an element's first line, and read what the page made of it."""
    box = page.locator(selector).first.bounding_box()
    select(
        page, (box["x"] + 4, box["y"] + 6), (box["x"] + box["width"] - 24, box["y"] + 6)
    )
    return page.evaluate(AFTER_THE_DRAG)


def test_the_label_is_chrome_rather_than_words_to_quote(site, hosted, browser):
    """The site's label is chrome, so selecting it must not offer a comment field."""
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        control = drag_across(page, "#decision-lede")
        assert control["fieldOffered"], "the page's own words raised no comment field"
        assert "monolith split" in control["quote"]

        label = drag_across(page, "main > .sitenote p")
        assert "example of a leaf page" in label["text"]
        assert not label["fieldOffered"]
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_shipped_log_opens_its_example_on_its_thread(site, hosted, browser):
    """An example that ships a log beside it arrives mid-conversation here too.

    The thread is the one thing no markup describes, so a copy of the markup could never
    carry one however it was written — which is what put every published example's
    comment loop out of reach until the pages went live. The session reads the log the
    build laid beside the versions into the runtime's first state answer, so the panel
    never renders an empty state and then fills in.

    The anchor is the half that rots quietly: the quote is captured against the file, and
    a rewritten sentence leaves it resolving to nothing and the thread standing detached,
    with no error anywhere."""
    page, errors = open_page(browser, example_url(hosted, "ship-review"))
    try:
        source = EXAMPLES / "ship-review.html"
        events = _parse_events(source.with_suffix(".jsonl").read_bytes())
        conversations = [
            thread
            for thread in build_threads(
                events, enclosing_ids(source.read_text(encoding="utf-8"))
            ).values()
            if not bare_reaction(thread)
        ]
        opened = sum(not thread["resolved"] for thread in conversations)
        resolved = len(conversations) - opened
        assert opened and resolved, "the shipped seed must cover both thread states"
        expect(page.locator(".lf-threads-toggle")).to_have_text(f"Threads ({opened})")
        page.locator(".lf-threads-toggle").click()
        expect(page.locator(".lf-panel .lf-details > summary")).to_have_text(
            f"Resolved ({resolved})"
        )
        # Named rather than taken first: the assertion follows the shipped objection,
        # independent of where a later seed might place another thread.
        thread = page.locator(".lf-panel .lf-thread").filter(
            has_text="One reconnect in forty is worse"
        )
        expect(thread).to_have_count(1)
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
            "the group renders on the site with nothing to press, so the decision "
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


def test_the_product_site_accepts_a_leaf_comment(site, hosted, browser):
    """The tour completes the same comment/projection loop as a published example."""
    page, errors = open_page(browser, product_url(hosted, "index.html"))
    try:
        box = page.locator("#lede").bounding_box()
        select(
            page,
            (box["x"] + 4, box["y"] + 8),
            (box["x"] + box["width"] - 40, box["y"] + box["height"] - 8),
        )
        expect(page.locator(".lf-fab-input")).to_be_visible()
        page.locator(".lf-composer textarea").fill("Can the page itself carry this?")
        page.keyboard.press("ControlOrMeta+Enter")

        thread = page.locator(
            ".lf-panel .lf-thread", has_text="Can the page itself carry this?"
        )
        expect(thread).to_contain_text("Can the page itself carry this?")
        expect(thread.locator("blockquote")).to_contain_text(
            "Your agent builds you the page"
        )
        expect(thread.locator('a[href="/#install"]')).to_have_count(1)
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
        # Selection offers the compact field without entering it, so the browser's
        # own selection is still there for a native copy.
        expect(page.locator(".lf-fab-input")).to_be_visible()
        page.locator(".lf-composer textarea").fill("Does this cover key rotation?")
        page.keyboard.press("ControlOrMeta+Enter")

        # The thread holding the words just written, rather than whichever is first:
        # an example that ships a log opens with threads already in the panel, and
        # theirs would be first. design-decision ships none today, so `.first` was
        # right by accident and would stop being on the day it does.
        thread = page.locator(
            ".lf-panel .lf-thread", has_text="Does this cover key rotation?"
        )
        expect(thread).to_contain_text("Does this cover key rotation?")
        expect(thread.locator("blockquote")).to_contain_text("session state homeless")
        expect(page.locator(".lf-threads-toggle")).to_have_text(
            f"Threads ({opened_with + 1})"
        )
        # The automated reply identifies itself and links to the real loop.
        reply = thread.locator(".lf-msg.claude")
        expect(reply.locator(".lf-msg-head b")).to_have_text("The demo")
        expect(reply.locator('a[href="/#install"]')).to_have_count(1)
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_static_demo_decision_resets_on_reload(site, hosted, browser):
    """The static site offers a live tab, not a second durable Leaf implementation.

    A gesture paints and is projected for the visit, while reload starts again from the
    checked-in example. Durable replay belongs to a served page's Python authority.
    """
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        chosen = (
            "() => [...document.querySelectorAll('lf-option[chosen]')].map(o => o.id)"
        )
        page.locator("#opt-jwt .lf-pick").click()
        expect(page.locator("#session-options")).to_have_attribute(
            "data-lf-reader-override", "1"
        )
        assert "opt-jwt" in page.evaluate(chosen)

        page.reload(wait_until="load")
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator("#session-options[data-lf-reader-override]")).to_have_count(
            0
        )
        assert "opt-jwt" not in page.evaluate(chosen), (
            "the static exhibit persisted a decision without a durable authority"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_the_static_demo_answers_the_exact_projection_path(site, hosted, browser):
    page, errors = open_page(browser, example_url(hosted, "design-decision"))
    try:
        answer = page.evaluate(
            """async () => {
              const state = await fetch('/api/state').then(response => response.json());
              const revision = state.active.revision;
              const through = state.browser.basis.through_seq;
              const response = await fetch(
                `/api/view?revision=${revision}&through_seq=${through}`,
              );
              return {status: response.status, through, body: await response.json()};
            }"""
        )
        assert answer["status"] == 200
        assert answer["body"]["browser"]["basis"] == {"through_seq": answer["through"]}
        assert set(answer["body"]["browser"]["views"]) == {"1"}
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
        page.locator(".lf-threads-toggle").click()  # the box lives in the panel
        page.locator(".lf-general textarea").fill("Where does this go?")
        page.locator(".lf-general .lf-btn.primary").click()
        # One, and typed: this example ships no log, so the count is the comment
        # just written and nothing else.
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (1)")
        # The page's own scroller (the runtime's `pageScroller`), moved the way a
        # reader moves it far enough down that the landmark is worth restoring.
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1500, behavior: 'instant'})"
        )
        assert page.evaluate("() => document.scrollingElement.scrollTop") > 0, (
            "the document did not scroll, so the landmark under test was never written"
        )

        # An example that ships no log of its own, so the count there is the reader's
        # own doing or nobody's. Asked of the corpus rather than named, since a page
        # that gains a companion log would otherwise turn this into a test of the seed.
        plain = next(
            p.stem for p in authored_examples() if not p.with_suffix(".jsonl").exists()
        )
        opened(page, errors, example_url(hosted, plain))
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")
        assert page.evaluate("() => document.scrollingElement.scrollTop") == 0, (
            "the ship review opened at the offset the reader left on another page"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_product_routes_do_not_share_page_state(site, hosted, browser):
    page, errors = open_page(browser, product_url(hosted, "index.html"))
    try:
        page.locator(".lf-threads-toggle").click()
        page.locator(".lf-general textarea").fill("This belongs to the tour.")
        page.locator(".lf-general .lf-btn.primary").click()
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (1)")
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1500, behavior: 'instant'})"
        )
        assert page.evaluate("() => document.scrollingElement.scrollTop") > 0

        opened(page, errors, product_url(hosted, "how-it-works.html"))
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")
        assert page.evaluate("() => document.scrollingElement.scrollTop") == 0
        assert not errors, errors[:3]
    finally:
        page.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_site_takes_its_palette_from_the_theme(site, hosted, browser, scheme):
    page = browser.new_page(color_scheme=scheme)
    errors = watched(page)
    try:
        for name in site_build.PRODUCT_ROUTES:
            opened(page, errors, product_url(hosted, name))
            assert (
                page.evaluate("getComputedStyle(document.body).backgroundColor")
                == (PAPER[scheme])
            ), name
            assert not errors, f"{name}: {errors[:3]}"
    finally:
        page.close()


def test_the_pages_fit_a_phone(site, hosted, browser):
    """Nothing scrolls sideways at 390px — the nav wraps, the screenshots scale,
    and a command too long for the column scrolls inside its own block.

    The site's own pages, not the examples it publishes: a page with a suggestion
    on it hangs the accept/reject controls in the margin, and at 390px
    there is no margin to hang them in. That is the live page's question rather
    than the site's, and it is not answered here."""
    page = browser.new_page(viewport=PHONE)
    errors = watched(page)
    try:
        for name in site_build.PRODUCT_ROUTES:
            opened(page, errors, product_url(hosted, name))
            overflow = page.evaluate(
                "() => { const b = document.body;"
                " return b.scrollWidth - b.clientWidth; }"
            )
            assert overflow <= 0, f"{name} scrolls {overflow}px sideways on a phone"
            assert not errors, f"{name}: {errors[:3]}"
    finally:
        page.close()
