"""The published site: what the build assembles, and what a reader gets.

The site is the repo's standalone product pages plus its examples and developer feature
gallery as live pages, so most of what could go wrong is a path that meant one thing in
a checkout and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP: product sources are rendered into self-contained files,
while each example uses its page-scoped vendored layer through the canonical server.
"""

import base64
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
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
FEATURE_GALLERY = EXAMPLES / "developer" / "feature-gallery.html"

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


def published_pages():
    """The worked examples plus the linked developer reference."""
    assert FEATURE_GALLERY.is_file(), "the feature gallery is missing"
    return [*authored_examples(), FEATURE_GALLERY]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """One build for the module: it vendors a layer and checks every published page."""
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
    """The canonical route for one exported product source."""
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


def test_product_pages_inline_the_composed_theme(site):
    """Authored sources use the Leaf scaffold; published copies need no stylesheet."""
    theme_halves = [
        ROOT / "skills" / "leaf" / "assets" / "theme.css",
        ROOT / "skills" / "leaf" / "packages" / "default" / "theme.css",
        *(
            ROOT / "skills" / "leaf" / "packages" / name / "theme.css"
            for name in json.loads((EXAMPLES / "layer.json").read_text())
        ),
        DOCS / "package" / "theme.css",
    ]
    assert all(source.is_file() for source in theme_halves)
    for page in pages_under(DOCS):
        target = site_build.product_target(site, site_build.PRODUCT_ROUTES[page.name])
        published = target.read_text()
        source_markup = page.read_text()
        assert source_markup.count('href="/theme.css"') == 1, page.name
        assert 'href="/theme.css"' not in published, page.name
        for theme in theme_halves:
            assert theme.read_text().rstrip() in published, (
                f"{page.name} is missing {theme.parent.name}'s theme"
            )


def test_product_pages_are_published_as_self_contained_copies(site):
    sources = pages_under(DOCS)
    assert {source.name for source in sources} == set(site_build.PRODUCT_ROUTES)
    for source in sources:
        target = site_build.product_target(site, site_build.PRODUCT_ROUTES[source.name])
        published = target.read_text()
        assert 'class="lf-copy' in published, source.name
        assert "<script" not in published, source.name
        assert "data-lf-reading" not in published, source.name
        assert 'src="/media/' not in published, source.name
        assert not (target.parent / "data.json").exists(), source.name
        assert not (target.parent / "events.jsonl").exists(), source.name


def test_only_canonical_examples_keep_a_runtime_layer(site):
    """Product exports inline their layer; shared media and the example note remain."""
    assert (site / "sitenote.js").read_bytes() == (DOCS / "sitenote.js").read_bytes()
    product_media = {
        Path(media_url(source)).name: source
        for source in (
            path
            for pattern in ("*.gif", "*.jpg", "*.png")
            for path in DOCS.glob(pattern)
        )
    }
    assert {path.name for path in (site / "media").iterdir()} == set(product_media)
    for name, source in product_media.items():
        target = site / "media" / name
        assert target.read_bytes() == source.read_bytes(), source.name
    for name in (
        "leaf.js",
        "session.js",
        "runtime.js",
        "theme.css",
        "registry.json",
        "icon.svg",
        "data.json",
        "events.jsonl",
    ):
        assert not (site / name).exists(), f"obsolete product runtime asset: {name}"
    for name in ("runtime", "widgets", "vendor"):
        assert not (site / name).exists(), f"obsolete product runtime directory: {name}"


def test_every_published_page_keeps_its_canonical_page_record(site):
    """Static routes are derived beside, rather than replacing, Leaf's page record."""
    for source in published_pages():
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


def test_a_website_example_keeps_its_version_identity_and_history(
    served_example, browser
):
    """The website adapter preserves the canonical server's version routes."""
    name = "log-retention"
    page_dir, url = served_example(name)
    events = read_events(page_dir)
    mappings = files_model.version_revisions(events)
    versions = [
        {
            "version": version,
            "revision": revision,
            "url": f"/examples/{name}/versions/v{version}.html",
        }
        for version, revision in sorted(mappings.items())
    ]
    page, errors = open_page(browser, url)
    try:
        expect(page.locator(".lf-version")).to_have_text("v2 ▾")
        current = page.evaluate("() => fetch('api/state').then(r => r.json())")
        assert current["active"]["revision"] == mappings[2]
        assert current["active"]["version"] == 2
        assert current["active"]["url"].startswith(
            f"/examples/{name}/revisions/r{mappings[2]}-"
        )
        assert current["active"]["label"] == "v2"
        assert current["versions"] == versions

        page.locator(".lf-version").click()
        expect(page.locator(".lf-version-row")).to_have_count(2)
        page.locator('.lf-version-diff[data-lf-version="1"]').click()
        expect(page.locator("main .lf-ins-block")).to_have_count(3)

        page.locator(".lf-version").click()
        page.locator('.lf-version-row[data-lf-version="1"]').click()
        page.wait_for_url(
            re.compile(r"/examples/log-retention/versions/v1\.html(?:\?pin=)?$")
        )
        page.wait_for_function(BOTH_STAMPS)

        expect(page.locator(".lf-version")).to_have_text("v1 ▾")
        expect(page.locator("#ret-cost-keep")).to_have_count(0)
        markup = page.evaluate(
            "() => fetch('../versions/v1.html').then(response => response.text())"
        )
        assert '<meta name="lf-version" data-lf-runtime content="1">' in markup
        assert (
            f'<meta name="lf-revision" data-lf-runtime content="{mappings[1]}">'
            in markup
        )
        pinned = page.evaluate("() => fetch('../api/state').then(r => r.json())")
        assert pinned["versions"] == versions
        assert errors == []
    finally:
        page.close()


def test_every_product_route_is_a_standalone_leaf_copy(site, hosted, browser):
    """Each product route is rendered, self-contained, and free of live controls."""
    names = list(site_build.PRODUCT_ROUTES)
    page = browser.new_page()
    errors = watched(page)
    failed = []
    page.on(
        "response",
        lambda response: (
            failed.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None
        ),
    )
    try:
        for name in names:
            page.goto(product_url(hosted, name), wait_until="load")
            expect(page.locator("html")).to_have_class(re.compile(r"\blf-copy\b"))
            assert page.evaluate("document.compatMode") == "CSS1Compat", name
            source = (DOCS / name).read_text(encoding="utf-8")
            expected_title = re.search(r"<title>(.*?)</title>", source, re.DOTALL)
            expected_h1 = re.search(r"<h1>(.*?)</h1>", source, re.DOTALL)
            assert expected_title and expected_h1
            assert page.title() == expected_title.group(1).strip(), name
            expect(page.locator("h1")).to_have_text(expected_h1.group(1).strip())
            expect(page.locator("script, .lf-chrome")).to_have_count(0)
            expect(page.locator('link[rel="stylesheet"]')).to_have_count(0)
            expect(page.locator("main > .sitenote")).to_have_count(0)
            if "<lf-toc" in source:
                assert page.locator("lf-toc a").count() > 0, (
                    f"{name}: the exported table of contents has no links"
                )
            assert page.locator("lf-specimen button").count() == 0, (
                f"{name}: a quoted specimen kept a live control"
            )
            assert not errors, f"{name}: {errors[:3]}"
            assert not failed, f"{name}: {failed[:3]}"
    finally:
        page.close()


def test_the_product_diagram_fits_without_its_own_scroll(hosted, browser):
    """The architecture is one sequence, so the diagram must fit its content box."""
    page = browser.new_page()
    errors = watched(page)
    try:
        page.set_viewport_size({"width": 1200, "height": 900})
        page.goto(product_url(hosted, "how-it-works.html"), wait_until="load")
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
        expect(page.locator("html")).to_have_class(re.compile(r"\blf-copy\b"))
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
            prefix, encoded = pair["image"].split(",", 1)
            assert prefix == "data:image/jpeg;base64"
            assert (
                base64.b64decode(encoded) == (DOCS / f"example-{stem}.jpg").read_bytes()
            )
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

        developer_galleries = page.locator("#developer-galleries")
        expect(developer_galleries).to_be_visible()
        developer_galleries.scroll_into_view_if_needed()
        expect(developer_galleries.locator("a.developer-gallery-link")).to_have_count(2)
        expect(page.locator("iframe, lf-tabs")).to_have_count(0)
        published = {
            path.name for path in (site / "examples").iterdir() if path.is_dir()
        }
        assert published == expected | {FEATURE_GALLERY.stem}
        assert page.evaluate(
            "() => Boolean(document.querySelector('#pages')"
            ".compareDocumentPosition(document.querySelector('#developer-galleries'))"
            " & Node.DOCUMENT_POSITION_FOLLOWING)"
        )
        product_gallery = developer_galleries.locator("#product-gallery")
        expect(product_gallery).to_contain_text("Product gallery")
        expect(product_gallery).to_have_attribute("href", "/examples/feature-gallery/")
        interaction_gallery = developer_galleries.locator("#interaction-gallery")
        expect(interaction_gallery).to_contain_text("Interaction gallery")
        expect(interaction_gallery).to_have_attribute(
            "href", "/examples/feature-gallery/#bg-interactions"
        )
        assert not errors, errors[:3]
    finally:
        page.close()


def test_the_interaction_gallery_drives_real_widgets(serve, browser):
    """The runner pauses its real widgets, resumes them, and resets between scenes.

    Playback calls each upgraded widget's canonical rendering surface without
    dispatching its input gesture, so a developer can inspect the transition without
    the demonstration becoming durable page state.
    """
    url = serve(FEATURE_GALLERY)
    page_dir = serve.page_dir
    page, errors = open_page(browser, f"{url}#bg-interactions")
    try:
        before = read_events(page_dir)
        gallery = page.locator("#bg-interactions")
        status = gallery.locator("[data-interaction-status]")
        toggle = gallery.locator("[data-interaction-toggle]")
        replay = gallery.locator("[data-interaction-replay]")
        accept = gallery.locator("#bg-motion-accept")
        card = gallery.locator("#bg-motion-card")

        expect(status).to_have_text("Accept a suggestion · Playing")
        expect(gallery.locator(".interaction-pointer").first).to_be_visible()
        toggle_box = toggle.bounding_box()
        assert toggle_box["y"] + toggle_box["height"] <= 900
        gallery.locator(".interaction-stage").first.evaluate(
            "stage => { window.pauseProbe = stage.animate([{}, {}], {duration: 10000}); }"
        )
        toggle.click()
        expect(status).to_have_text("Accept a suggestion · Paused")
        assert page.evaluate("window.pauseProbe.playState") == "paused"
        page.wait_for_timeout(800)
        assert accept.get_attribute("data-lf-state") is None
        toggle.click()
        assert page.evaluate("window.pauseProbe.playState") == "running"
        page.evaluate("window.pauseProbe.cancel()")
        expect(status).to_have_text("Accept a suggestion · Complete", timeout=10_000)
        expect(toggle).to_have_text("Played")
        expect(toggle).to_be_disabled()
        expect(replay).to_be_enabled()
        assert gallery.evaluate(
            """async gallery => {
                const { pageWords, says } = await import('/runtime/passages.js');
                const toggle = gallery.querySelector('[data-interaction-toggle]');
                const status = gallery.querySelector('[data-interaction-status]');
                return !pageWords(toggle.firstChild)
                    && !pageWords(status.firstChild)
                    && !says(gallery).includes(status.textContent);
            }"""
        )
        assert gallery.locator(
            ".interaction-control, .interaction-status"
        ).evaluate_all(
            "nodes => nodes.map(node => getComputedStyle(node).fontSize)"
        ) == ["11.5px", "11.5px", "11.5px"]
        expect(accept).to_have_attribute("data-lf-state", "accept")
        assert read_events(page_dir) == before

        move_tab = gallery.get_by_role("tab", name="Move a card")
        move_tab.click()
        expect(status).to_have_text("Move a card · Complete", timeout=10_000)
        assert card.evaluate("card => card.parentElement.id") == "bg-motion-tried"
        assert move_tab.evaluate("tab => document.activeElement === tab")
        assert read_events(page_dir) == before

        gallery.locator("[data-interaction-replay]").click()
        expect(status).to_have_text("Move a card · Playing")
        assert card.evaluate("card => card.parentElement.id") == "bg-motion-ready"
        assert card.evaluate("card => card.getAnimations().length") == 0
        expect(status).to_have_text("Move a card · Complete", timeout=10_000)
        assert card.evaluate("card => card.parentElement.id") == "bg-motion-tried"
        assert read_events(page_dir) == before
        page.set_viewport_size({"width": 390, "height": 844})
        assert gallery.locator("#bg-motion-board").evaluate(
            "board => board.scrollWidth === board.clientWidth"
        )
        assert gallery.locator("#bg-motion-board").evaluate(
            "board => getComputedStyle(board).gridAutoFlow === 'row'"
        )
        assert status.evaluate("status => getComputedStyle(status).marginLeft") == "0px"

        replacement_installed = gallery.evaluate(
            """gallery => {
                const replacement = gallery.cloneNode(true);
                replacement.removeAttribute('data-interaction-installed');
                replacement.querySelector('.interaction-controls')?.remove();
                gallery.replaceWith(replacement);
                document.dispatchEvent(new Event('lf-actions'));
                return new Promise(resolve => requestAnimationFrame(() =>
                    resolve(replacement.dataset.interactionInstalled === '1')
                ));
            }"""
        )
        assert replacement_installed
        page.emulate_media(media="print")
        expect(toggle).to_be_hidden()
        expect(replay).to_be_hidden()
        assert not errors, errors[:3]
    finally:
        page.close()


def test_reduced_motion_leaves_gallery_play_explicit(serve, browser):
    url = serve(FEATURE_GALLERY)
    context = browser.new_context(
        reduced_motion="reduce", viewport={"width": 1280, "height": 900}
    )
    page, errors = open_page(browser, f"{url}#bg-interactions", context=context)
    try:
        gallery = page.locator("#bg-interactions")
        status = gallery.locator("[data-interaction-status]")
        accept = gallery.locator("#bg-motion-accept")
        expect(status).to_have_text(
            "Accept a suggestion · Ready — motion will start only when you press Play"
        )
        page.wait_for_timeout(900)
        assert accept.get_attribute("data-lf-state") is None
        gallery.locator("[data-interaction-toggle]").click()
        expect(status).to_have_text("Accept a suggestion · Complete", timeout=10_000)
        expect(accept).to_have_attribute("data-lf-state", "accept")
        assert not errors, errors[:3]
    finally:
        context.close()


def test_every_published_page_stands_as_a_live_page(served_example, browser):
    """Every artifact starts through Leaf's own document and state boundaries."""
    pages = published_pages()
    _, url = served_example(pages[0].stem)
    page, errors = open_page(browser, url)
    try:
        for source in pages:
            if source != pages[0]:
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
        decisions = page.locator(".lf-asks")
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
        decisions = page.locator(".lf-asks")
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


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_site_takes_its_palette_from_the_theme(site, hosted, browser, scheme):
    page = browser.new_page(color_scheme=scheme)
    errors = watched(page)
    try:
        for name in site_build.PRODUCT_ROUTES:
            page.goto(product_url(hosted, name), wait_until="load")
            assert (
                page.evaluate("getComputedStyle(document.body).backgroundColor")
                == (PAPER[scheme])
            ), name
            assert not errors, f"{name}: {errors[:3]}"
    finally:
        page.close()


def test_the_pages_fit_a_phone(site, hosted, browser):
    """Nothing scrolls sideways at 390px — the nav wraps, the screenshots scale,
    and a command too long for the column scrolls inside its own block."""
    page = browser.new_page(viewport=PHONE)
    errors = watched(page)
    try:
        for name in site_build.PRODUCT_ROUTES:
            page.goto(product_url(hosted, name), wait_until="load")
            overflow = page.evaluate(
                "() => { const b = document.body;"
                " return b.scrollWidth - b.clientWidth; }"
            )
            assert overflow <= 0, f"{name} scrolls {overflow}px sideways on a phone"
            assert not errors, f"{name}: {errors[:3]}"
    finally:
        page.close()
