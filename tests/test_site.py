"""The published site: what the build assembles, and what a reader gets.

The site is the repo's own pages plus every example as a live page, so most of what
could go wrong is a path that meant one thing in a checkout and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP: product sources use the site's root layer, while each
example uses its page-scoped vendored layer through the canonical server. file:// is no
longer a second supported document mode for either one.
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
from example_data import data_operations, example_versions
from interact_support import SHIPPED_PACKAGES
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf.event_log import _parse_events, read_events
from leaf.events import bare_reaction, build_threads
from leaf.passages import enclosing_ids
from playwright.sync_api import expect

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/CLAUDE.md, "A wait consumes a fact the system states".
from render_support import BOTH_STAMPS, navigate, open_page, select, sending, watched

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "skills" / "leaf" / "assets"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"

_spec = importlib.util.spec_from_file_location("site", ROOT / "scripts" / "site.py")
site_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site_build)
_server_spec = importlib.util.spec_from_file_location(
    "website_server", ROOT / "worker" / "server.py"
)
website_server = importlib.util.module_from_spec(_server_spec)
_server_spec.loader.exec_module(website_server)

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


@pytest.fixture
def served_example(site, tmp_path):
    """Serve one browser's disposable pages through the website's real backend."""
    session_site = tmp_path / "site"
    examples = session_site / "examples"
    examples.mkdir(parents=True)
    shutil.copy2(site / "sitenote.js", session_site / "sitenote.js")
    httpd = hosting_model.server_at(
        "127.0.0.1", 0, website_server.handler_for(examples)
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"

    def serve(name):
        page_dir = examples / name
        shutil.copytree(site / "examples" / name, page_dir)
        return page_dir, f"{origin}/examples/{name}/"

    yield serve
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


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


def test_every_example_is_a_complete_canonical_page_directory(site):
    """The published artifact is directly servable by Leaf, with no static surrogate."""
    for source in authored_examples():
        page_dir = site / "examples" / source.stem
        versions = example_versions(source)
        events = read_events(page_dir)
        mappings = files_model.version_revisions(events)
        operations = data_operations(source)
        stored_data = json.loads((page_dir / "data.json").read_text())

        assert (page_dir / "index.html").read_bytes() == versions[-1].read_bytes()
        assert files_model.published_versions(page_dir, events) == list(
            range(1, len(versions) + 1)
        )
        for number, authored in enumerate(versions, start=1):
            revision = files_model.revision_path(page_dir, mappings[number])
            assert revision.read_bytes() == authored.read_bytes(), (
                f"{authored.name} changed while it was published"
            )

        seed = source.with_suffix(".jsonl")
        if seed.exists():
            assert seed.read_text() in (page_dir / "events.jsonl").read_text()
            assert json.loads((page_dir / "cursor.json").read_text()) == {
                "seq": len(events)
            }
        else:
            assert not (page_dir / "cursor.json").exists()
        assert set(stored_data["sources"]) == {
            operation["source"] for operation in operations
        }
        for operation in operations:
            if operation["kind"] == "set":
                assert (
                    stored_data["sources"][operation["source"]]["value"]
                    == operation["value"]
                )

        for name in (
            "data.json",
            "events.jsonl",
            "icon.svg",
            "leaf.js",
            "registry.json",
            "status.json",
            "theme.css",
        ):
            assert (page_dir / name).is_file(), f"{source.name}: no {name}"
        for sub in ("guidance", "media", "revisions", "runtime", "vendor", "widgets"):
            assert list((page_dir / sub).iterdir()), f"{source.name}: {sub}/ is empty"
        assert json.loads((page_dir / "status.json").read_text())["state"] == "idle"
        assert not (page_dir / "service.json").exists()
        assert not (page_dir / "preview.json").exists()
        assert not (page_dir / "versions").exists()


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


def test_every_example_stands_as_a_live_page(served_example, browser):
    """Every artifact starts through Leaf's own document and state boundaries."""
    examples = authored_examples()
    _, url = served_example(examples[0].stem)
    page, errors = open_page(browser, url)
    try:
        for source in examples:
            if source != examples[0]:
                _, url = served_example(source.stem)
                opened(page, errors, url)
            newest = len(example_versions(source))
            expect(page.locator(".lf-banner .lf-version")).to_have_text(f"v{newest} ▾")
            expect(page.locator(".lf-status-text")).to_have_text(
                "This is an example on the Leaf website. No agent will respond. "
                "Install Leaf"
            )
            assert not errors, f"{source.name}: {errors[:3]}"

    finally:
        page.close()


def test_an_example_paints_while_every_stage_of_site_startup_is_held(
    served_example, browser
):
    """Authored HTML paints before JavaScript or server state is ready.

    Holding /leaf.js proves widget upgrade cannot be what made the document visible.
    The waiting pseudo-element's computed content proves the loading sheet does not
    exist, without waiting for an animation threshold. Once JavaScript starts, holding
    /api/state proves the data-bound diff waits for the backend's canonical projection.
    """
    boot = []
    state = []
    _, url = served_example("pr-walkthrough")
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/leaf.js", lambda route: boot.append(route))
    page.route("**/api/state*", lambda route: state.append(route))

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        expect(page.locator("h1")).to_have_text(example_title("pr-walkthrough"))
        expect(page.locator("h1")).to_be_visible()

        assert boot, "the positive control did not hold the site boot module"
        expect(page.locator("body > main")).to_have_css("pointer-events", "auto")
        assert (
            page.evaluate("() => getComputedStyle(document.body, '::after').content")
            == "none"
        ), "the waiting sheet painted before the site boot module arrived"

        with page.expect_request("**/api/state*"):
            boot.pop().continue_()

        assert page.locator("body").get_attribute("data-lf-presented") is None
        assert state, "the canonical state request was not still in flight"
        expect(page.locator("#pr-exact-patch")).not_to_have_class(
            re.compile(r"\blf-rendered\b")
        )
        expect(page.locator("#pr-exact-patch details")).to_have_count(0)

        for route in state:
            route.continue_()
        state.clear()
        page.wait_for_load_state("load")
        expect(page.locator("#pr-exact-patch")).to_have_class(
            re.compile(r"\blf-rendered\b")
        )
        expect(page.locator("#pr-exact-patch details").first).to_be_visible()
        page.wait_for_function(BOTH_STAMPS)
        assert errors == []
    finally:
        for route in boot:
            route.continue_()
        for route in state:
            route.continue_()
        page.unroute_all(behavior="wait")
        page.close()


def test_a_published_example_has_no_agent_claim(served_example, browser):
    """A finished public page claims neither an agent nor an active session."""
    page_dir, url = served_example("design-decision")
    page, errors = open_page(browser, url)
    try:
        expect(page.locator(".lf-banner .lf-status-text")).to_have_text(
            "This is an example on the Leaf website. No agent will respond. "
            "Install Leaf"
        )
        expect(page.locator(".lf-banner .lf-status-text a")).to_have_attribute(
            "href", "/#install"
        )
        expect(page.locator("main > .sitenote")).to_contain_text(
            "Try its controls in a private, temporary copy for this browser."
        )
        assert page.locator("main > .sitenote a").evaluate_all(
            "links => links.map(link => link.getAttribute('href'))"
        ) == ["/", "/examples/", "/#install"]
        expect(page.locator(".lf-banner .lf-dot")).to_have_class(
            re.compile(r"^lf-dot\s*$")
        )
        state = page.evaluate("() => fetch('api/state').then(r => r.json())")
        assert state["example"] == {"install_url": "/#install"}
        assert state["claims"] == []
        assert state["host"] is None
        assert state["session_alive"] is None
        assert not state["listening"]
        assert not (page_dir / "service.json").exists()
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_shipped_log_opens_its_example_on_its_thread(served_example, browser):
    """An example that ships a log arrives mid-conversation through the real projection.

    The thread is the one thing no markup describes, so a copy of the markup could never
    carry one however it was written. Leaf reads the complete page directory's log into
    the runtime's first state answer, so the panel never renders empty and then fills in.

    The anchor is the half that rots quietly: the quote is captured against the file, and
    a rewritten sentence leaves it resolving to nothing and the thread standing detached,
    with no error anywhere."""
    _, url = served_example("ship-review")
    page, errors = open_page(browser, url)
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
        # The question Claude asks in that thread is a widget, upgraded from the
        # same canonical state a reader can answer where they are standing.
        ask = page.locator("#off-slip")
        expect(ask).to_be_visible()
        assert ask.locator("[data-lf-offer]").count() > 0, (
            "the group renders on the site with nothing to press, so the decision "
            "is a picture of one"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_shipped_data_snapshot_opens_in_its_package_projection(
    site, served_example, browser
):
    """The page backend delivers package data through the live state contract."""
    stored = json.loads((site / "examples" / "command-hub" / "data.json").read_text())
    assert (
        stored["sources"]["atlas-worktrees"]["value"]["tree-w-1"]["branch"]
        == "atlas/xml-declarations"
    )

    _, url = served_example("command-hub")
    page, errors = open_page(browser, url)
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


def test_a_comment_persists_without_inventing_an_agent_reply(served_example, browser):
    """The real backend stores the reader's anchored words without impersonating an agent."""
    _, url = served_example("design-decision")
    page, errors = open_page(browser, url)
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
        with sending(page, "the anchored comment"):
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
        expect(thread.locator(".lf-msg.claude")).to_have_count(0)
        page.reload(wait_until="load")
        page.wait_for_function(BOTH_STAMPS)
        thread = page.locator(
            ".lf-panel .lf-thread", has_text="Does this cover key rotation?"
        )
        expect(thread).to_contain_text("Does this cover key rotation?")
        expect(thread.locator("blockquote")).to_contain_text("session state homeless")
        expect(thread.locator(".lf-msg.claude")).to_have_count(0)
        assert not errors, errors[:3]
    finally:
        page.close()


def test_the_published_page_counts_every_declared_ask(served_example, browser):
    """The inventory includes request Decisions and excludes aggregate roll-ups."""
    _, url = served_example("command-hub")
    page, errors = open_page(browser, url)
    try:
        decisions = page.locator(".lf-decisions")
        expect(decisions).to_be_visible()
        expect(decisions).to_have_text("Asks 0/5")
        assert not errors, errors[:3]
    finally:
        page.close()


def test_a_published_decision_survives_reload(served_example, browser):
    """A published example uses Leaf's durable log rather than browser-only state."""
    _, url = served_example("design-decision")
    page, errors = open_page(browser, url)
    try:
        decisions = page.locator(".lf-decisions")
        expect(decisions).to_be_visible()
        expect(decisions).to_have_text("Asks 0/2")
        chosen = (
            "() => [...document.querySelectorAll('lf-option[chosen]')].map(o => o.id)"
        )
        with sending(page, "the published option pick"):
            page.locator("#opt-jwt .lf-pick").click()
        expect(page.locator("#session-options")).to_have_attribute(
            "data-lf-reader-override", "1"
        )
        assert "opt-jwt" in page.evaluate(chosen)
        expect(decisions).to_have_text("Asks 1/2")
        page.reload(wait_until="load")
        page.wait_for_function(BOTH_STAMPS)
        expect(decisions).to_have_text("Asks 1/2")
        assert "opt-jwt" in page.evaluate(chosen)
        assert not errors, errors[:3]
    finally:
        page.close()


def test_the_page_backend_answers_the_exact_projection_path(served_example, browser):
    _, url = served_example("design-decision")
    page, errors = open_page(browser, url)
    try:
        answer = page.evaluate(
            """async () => {
              const state = await fetch('api/state').then(response => response.json());
              const revision = state.active.revision;
              const through = state.browser.basis.through_seq;
              const response = await fetch(
                `api/view?revision=${revision}&through_seq=${through}`,
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


def test_what_a_reader_leaves_on_one_page_stays_on_it(served_example, browser):
    """Independent page backends do not share their logs or reading positions."""
    _, url = served_example("design-decision")
    page, errors = open_page(browser, url)
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
        _, plain_url = served_example(plain)
        opened(page, errors, plain_url)
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")
        assert page.evaluate("() => document.scrollingElement.scrollTop") == 0, (
            "the second example opened at the offset left on the first"
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
