"""The published site: what the build assembles, and what a user gets.

The site is the repo's product pages, examples, and developer feature gallery as live
Leaf pages, so most of what could go wrong is a path that meant one thing in a checkout
and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP through its page-scoped vendored layer and the canonical
server.
"""

import functools
import html as html_module
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import leaf_website as website_server
import pytest
from conftest import LENT_LINKED_DIRS
from interact_support import declared, running_http_server, wait_for
from leaf_dev.browser import panel_tab
from leaf_dev.commands import site as site_build
from leaf_dev.example_data import catalog_sources, data_operations, example_versions
from leaf_dev.leaf_assets import pinned_assets
from leaf_dev.page_fixtures import authored_markup, source_packages
from PIL import Image
from playwright.sync_api import expect
from render_harness import (
    OPEN_THREAD_COUNT,
    PANEL_THREAD,
    compare_with,
    consume_browser_errors,
    displayed,
    expect_obligations_answered,
    expect_open_threads,
    holding,
    http_error_console,
    is_problem,
    navigate,
    open_page,
    open_threads,
    page_comment,
    panel_menu,
    root_overflow,
    select,
    sending,
    take_browser_errors,
    write,
)

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/AGENTS.md, "Waits".
from journeys import expect_showing
from leaf import data as data_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import layer as layer_model
from leaf import schema as schema_model
from leaf.event_log import _parse_events, read_events
from leaf.events import bare_reaction, build_threads
from leaf.passages import enclosing_ids
from leaf.registry.storage import layer_packages, layer_record, selected
from leaf.render_checks import wait_until_ready
from leaf.render_gate import version as render_gate_model
from leaf.revision_artifact import read_artifact
from leaf.service import acknowledged
from leaf.structure import SourceDocument

ROOT = Path(__file__).parents[2]
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
FEATURE_GALLERY = EXAMPLES / "developer" / "feature-gallery.html"
DEVELOPER_PAGES = tuple(sorted((EXAMPLES / "developer").glob("*.html")))


def open_count(page):
    """How many open threads the page's reading holds (`OPEN_THREAD_COUNT`), once its
    saved inventory has arrived."""
    return wait_for(
        lambda: page.evaluate(OPEN_THREAD_COUNT),
        lambda held: held is not None,
        failure="the page's saved threads never arrived",
    )


# The theme's paper, light and dark, as the browser reports a background.
PAPER = {"light": "rgb(250, 249, 245)", "dark": "rgb(25, 24, 21)"}
PHONE = {"width": 390, "height": 844}


# The module-scoped build and host are one shared setup, so they belong to one
# xdist work unit rather than being rebuilt independently on every worker.
pytestmark = [pytest.mark.shifts_unsurveyed, pytest.mark.xdist_group(name="site")]


def sample_address(frame):
    """The child's HTTP root, independent of private bootstrap fragment settings."""
    return (frame.get_attribute("src") or "\0").partition("#")[0]


def sample_allocation(page, url, template):
    """Capture a template's child root before its allocation response is delivered.

    Request callbacks read this producer-owned URL rather than querying iframe DOM
    while a reload or mount may still be replacing it.
    """
    allocation = {"url": None}

    def allocated(route):
        if route.request.post_data_json["template"] == template:
            response = route.fetch()
            allocation["url"] = urljoin(url, response.json()["url"])
            route.fulfill(response=response)
        else:
            route.continue_()

    page.route("**/api/samples", allocated)
    return allocation


def pages_under(directory):
    """The pages a sweep walks, proved to exist before it walks them. Four of the
    checks below are loops over a glob and nothing else, so a directory that moved or
    was renamed turns every one of them into a sweep that pressed nothing — green, and
    for the wrong reason (tests/AGENTS.md, "Sweeps over controls")."""
    pages = sorted(directory.glob("*.html"))
    assert pages, f"no pages under {directory}"
    return pages


def heading(source: str) -> str:
    """The words of the h1 an authored source carries, as the parser reads them."""
    return " ".join(SourceDocument(source).tree.select_one("h1").text.split())


def example_title(stem: str) -> str:
    """The h1 an example's own source carries, so a retitled example cannot strand a
    test on its old words."""
    return heading((EXAMPLES / f"{stem}.html").read_text(encoding="utf-8"))


def authored_examples():
    """The public examples, excluding any generated browser-stress snapshot."""
    pages = pages_under(EXAMPLES)
    authored = [page for page in pages if page.stem != "corpus"]
    assert authored, "no authored examples to publish"
    return authored


def framed_root_examples():
    """Every example whose `main` is a workspace (`.layout-workspace`).

    Derived rather than listed, so a new one is gated without naming it here. The
    reading is `leaf.structure`'s, the one `page check` admits and the browser
    takes, so an omitted `</p>` cannot split the two counts.
    """
    framed = []
    for page in authored_examples():
        parsed = SourceDocument(page.read_text(encoding="utf-8"))
        main = next(node for node in parsed.authoring.nodes if node["tag"] == "main")
        if "layout-workspace" in main["attrs"].get("class", "").split():
            framed.append(page.stem)
    assert framed, "the corpus published no framed-root example to check"
    return sorted(framed)


def published_pages():
    """The worked examples plus the linked developer reference."""
    assert FEATURE_GALLERY in DEVELOPER_PAGES, "the core feature gallery is missing"
    return [*authored_examples(), *DEVELOPER_PAGES]


@pytest.fixture(name="site", scope="module")
def site(tmp_path_factory):
    """One build for the module: it vendors a layer and checks every published page."""
    out = tmp_path_factory.mktemp("published") / "site"
    site_build.build(out, site_build.checkout_leaf())
    return out


class ReleasedAssetEndpoint(website_server.WebsitePageEndpoint):
    """The container adapter with the edge's release namespace in front of it.

    One public origin is two servers in production: `worker/src/index.ts` answers
    `/_leaf-release/<release>/<key>/…` out of the build's sibling asset tree and
    hands every other route to this adapter, inside the user's own container.
    A sample captures that release namespace as its asset root, so a child page
    this adapter serves names dependencies only the edge holds; a fixture standing
    the adapter up alone serves a document whose runtime nothing answers for.

    The rewrite is `releaseAssetRoute`'s: the key after the release names the page,
    and what follows it is that page's own published path under the asset tree. The
    delivery headers are `stampDelivery`'s, which the runtime's probes read.
    """

    def __init__(self, request, server, *, asset_tree: Path, **bound) -> None:
        super().__init__(request, server, **bound)
        self.asset_tree = asset_tree

    def _select_page(self):
        released = self._released_asset()
        return released if released is not None else super()._select_page()

    def _released_asset(self):
        for public_root, page in self.pages.items():
            prefix = f"{page['assets']}/"
            if not self.path.startswith(prefix):
                continue
            root = "" if public_root == "/" else public_root
            file = (
                self.asset_tree / root.lstrip("/") / self.path[len(prefix) :]
            ).resolve()
            if not file.is_relative_to(self.asset_tree) or not file.is_file():
                return self._not_found()
            ctype = schema_model.CONTENT_TYPES[file.suffix]
            if ctype not in schema_model.BINARY_TYPES:
                ctype += "; charset=utf-8"
            response = self._content(200, ctype, file.read_bytes())
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Expose-Headers": "*",
                    "Leaf-Layer": page["layer"],
                    "Leaf-Release": self.release,
                }
            )
            return response
        return None


def released_site_endpoint(session_site: Path, asset_tree: Path):
    """The adapter's own binding, plus the asset tree the edge would answer from."""
    bound = website_server.site_endpoint(session_site)
    return functools.partial(
        ReleasedAssetEndpoint, asset_tree=asset_tree.resolve(), **bound.keywords
    )


@pytest.fixture(name="hosted", scope="module")
def hosted(site, tmp_path_factory):
    """One user's private copy, matching the container boundary in production."""
    session_site = tmp_path_factory.mktemp("website-session") / "site"
    shutil.copytree(site, session_site)
    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        released_site_endpoint(session_site, site_build.asset_site(site)),
    )
    with running_http_server(httpd):
        yield f"http://127.0.0.1:{httpd.server_address[1]}"


@pytest.fixture(name="served_example")
def served_example(site, tmp_path):
    """Serve one browser's disposable pages through the website's real backend."""
    session_site = tmp_path / "site"
    examples = session_site / "examples"
    examples.mkdir(parents=True)
    manifest = session_site / website_server.SITE_MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(site / website_server.SITE_MANIFEST, manifest)
    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        released_site_endpoint(session_site, site_build.asset_site(site)),
    )
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"

    def serve(name):
        page_dir = examples / name
        shutil.copytree(site / "examples" / name, page_dir)
        return page_dir, f"{origin}/examples/{name}/"

    with running_http_server(httpd):
        yield serve


def product_url(hosted, name):
    """The canonical route for one product source."""
    return hosted + site_build.product_route(Path(name))


media_url = site_build.media_url


def active_revision_directory(page_dir):
    revision = files_model.latest_revision(page_dir)
    assert revision is not None, f"{page_dir} has no published revision"
    return Path("revisions") / files_model.revision_path(page_dir, revision).stem


def opened(page, url):
    """A navigation this module makes for itself, waiting on what `open_page` waits
    on — the document's stamp and the log's — since a page at the first alone has a
    chrome the user would not recognize (tests/AGENTS.md)."""
    navigate(page, url, wait_until="load")


def test_product_pages_select_the_sources_packages(site):
    """Publication and local previews compose the product source's same layer."""
    for page in pages_under(DOCS):
        target = site_build.product_page(site, page.name)
        source_markup = page.read_text()
        assert 'href="/theme.css"' not in source_markup, page.name
        assert layer_packages(target) == source_packages(page), page.name


@pytest.mark.parametrize("name", ["index", "event-log", "how-it-works"])
def test_published_product_page_renders(site, browser, name):
    """The render gate passes the published product pages: the landing page, a
    reference page of prose, tables, code and a sample, and the page that holds
    every widget the docs use. The other routes share their sheet and parts, and
    `test_every_product_route_is_a_live_leaf_page` opens each of them."""
    product = site_build.product_page(site, f"{name}.html")
    with hosting_model.TemporaryPageServer(product) as server:
        url = f"{server.origin}/versions/v1.html?t={server.token}"
        failures = render_gate_model.render_version(browser, url).failures
    assert failures == [], "\n".join(map(str, failures))


def test_published_examples_keep_the_site_theme_out_of_their_layer(site, monkeypatch):
    """A website example uses the authored example's layout layer."""
    monkeypatch.chdir(ROOT)  # resolve project-relative package selections
    package = DOCS / "package"
    context_theme = layer_model.stylesheet(package / "theme.css", package).rstrip()
    for source in site_build.published_page_sources():
        record = layer_record(site / "examples" / source.stem)
        theme = (
            selected(record, site / "examples" / source.stem)
            .top_files["theme.css"]
            .decode()
        )
        assert context_theme not in theme, source


def test_published_example_has_the_normal_leaf_layout(hosted, browser, serve):
    source = EXAMPLES / "wt-merge.html"
    normal = open_page(browser, serve(source))
    published = open_page(browser, f"{hosted}/examples/wt-merge/")
    layout = """() => Object.fromEntries(
      ['.lf-floating-panel', 'body > main', 'body > main h1', '#lede', 'lf-merge-film']
        .map(selector => {
          const node = document.querySelector(selector);
          const box = node.getBoundingClientRect();
          const style = getComputedStyle(node);
          return [selector, {
            box: [box.x, box.y, box.width, box.height],
            padding: style.padding,
            font: style.fontFamily,
          }];
        }))"""
    for width in (390, 1200):
        for page in (normal, published):
            page.set_viewport_size({"width": width, "height": 900})
            wait_until_ready(page)
        assert published.evaluate(layout) == normal.evaluate(layout)


def test_product_pages_are_published_as_complete_page_records(site):
    """Each page retains its layer selection, history, and every captured media
    input."""
    sources = pages_under(DOCS)
    for source in sources:
        page = site_build.product_page(site, source.name)
        expected = authored_markup(source)
        assert (page / "index.html").read_text() == expected, source.name
        for name in (schema_model.LAYER_FILE, "events.jsonl"):
            assert (page / name).is_file(), f"{source.name}: no {name}"
        # The layer and runtime are the serving Leaf's, which the release publishes
        # beside each revision rather than the page holding them
        # (`runtime_selection`).
        assert list((page / "revisions").iterdir()), f"{source.name}: no revisions"
        artifact = read_artifact(page, files_model.latest_revision(page))
        for path, resource in artifact.resources.items():
            if path.startswith("/media/"):
                assert (page / path.lstrip("/")).read_bytes() == resource.data
        assert declared(page)["state"] == "idle"


def test_page_layers_stay_inside_their_page_directories(site):
    """The container image keeps complete pages rather than a public layer beside them."""
    for name in (
        *schema_model.VENDORED_FILES,
        "session.js",
        "runtime.js",
        "events.jsonl",
    ):
        assert not (site / name).exists(), f"unscoped runtime asset: {name}"
    for name in ("runtime", "widgets", "vendor"):
        assert not (site / name).exists(), f"unscoped runtime directory: {name}"


def test_the_asset_site_is_the_live_immutable_half_of_each_page(site):
    """The edge gets served Leaf documents and browser assets, never session state."""
    assets = site_build.asset_site(site)
    pinned = pinned_assets()
    root_media = SourceDocument(
        authored_markup(DOCS / "index.html")
    ).authoring.media_refs
    root_media.add(media_url(pinned / site_build.SOCIAL_CARD))
    product_media = {
        Path(media_url(source)).name: source
        for source in (
            pinned / site_build.SOCIAL_CARD,
            *(
                pinned / "examples" / f"example-{page.stem}.jpg"
                for page in catalog_sources()
            ),
        )
        if media_url(source) in root_media
    }
    assert {path.name for path in (assets / "media").iterdir()} == set(product_media)
    for name, source in product_media.items():
        assert (assets / "media" / name).read_bytes() == source.read_bytes()

    example_root = assets / "examples" / "triage-board"
    document = (example_root / "index.html").read_text(encoding="utf-8")
    manifest = json.loads((assets / site_build.SITE_MANIFEST).read_text())
    release = manifest["release"]
    asset_root = manifest["pages"]["/examples/triage-board"]["assets"]
    revision = active_revision_directory(site / "examples" / "triage-board")
    example_layer = example_root / revision
    assert 'data-lf-server="published"' in document
    assert f'data-lf-release="{release}"' in document
    assert f'src="{asset_root}/{revision}/leaf.js"' in document
    assert "sitenote.js" not in document
    assert (example_layer / "runtime" / "check-api.js").is_file()
    assert (example_layer / "registry.json").is_file()
    assert list((example_root / "versions").glob("v*.html"))
    assert list((example_root / "revisions").glob("r*.html"))
    for private in ("data", "events.jsonl", "stream.json"):
        assert not (example_root / private).exists()

    notification_root = assets / "examples" / "notification-playground"
    notification = manifest["pages"]["/examples/notification-playground"]
    notification_document = (notification_root / "index.html").read_text()
    notification_revision = active_revision_directory(
        site / "examples" / "notification-playground"
    )
    assert (
        f'from "{notification["assets"]}/{notification_revision}/runtime/widget-api.js"'
        in notification_document
    )

    # Public paths remain page-scoped, but repeated immutable payload bytes occupy one
    # inode in the build and container image rather than one complete copy per page.
    repeated = [
        assets
        / active_revision_directory(site_build.product_page(site, "index.html"))
        / "runtime"
        / "widget-api.js",
        example_layer / "runtime" / "widget-api.js",
    ]
    assert repeated[0].read_bytes() == repeated[1].read_bytes()
    assert repeated[0].stat().st_ino == repeated[1].stat().st_ino

    gallery_page = site / "examples" / "feature-gallery"
    gallery = manifest["pages"]["/examples/feature-gallery"]
    revisions = files_model.list_revisions(gallery_page)
    assert set(gallery["states"]) == {str(revision) for revision in revisions}
    assert (
        gallery["state"]
        == gallery["states"][str(files_model.latest_revision(gallery_page))]
    )
    for revision, state_path in gallery["states"].items():
        state = json.loads((assets / state_path.lstrip("/")).read_text())
        assert revision in state["browser"]["views"]
        assert state["release"] == release


def test_a_crawler_is_given_one_page_per_route(site):
    """The site publishes each page three times over, and says so once.

    A page stands at its clean route, at every stamped version, and at every
    revision. Only the first is a page a user should be sent to, so every
    document a page publishes names that route as its canonical.
    """
    assets = site_build.asset_site(site)
    manifest = json.loads((assets / site_build.SITE_MANIFEST).read_text())
    sitemap = (assets / "sitemap.xml").read_text(encoding="utf-8")
    robots = (assets / "robots.txt").read_text(encoding="utf-8")

    assert f"Sitemap: {site_build.SITE_ORIGIN}/sitemap.xml" in robots
    # Silence is not neutral here: a zone that states no signal is given
    # `ai-train=no` by Cloudflare's managed robots.txt. This site permits all three.
    assert "Content-Signal: search=yes, ai-input=yes, ai-train=yes" in robots
    assert "Disallow" not in robots
    listed = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    routes = {
        f"{site_build.SITE_ORIGIN}{'' if route == '/' else route}/"
        for route in manifest["pages"]
    }
    assert listed == routes

    for route, page in manifest["pages"].items():
        page_root = "" if route == "/" else route
        destination = assets / page_root.lstrip("/")
        documents = [
            destination / "index.html",
            *sorted((destination / "versions").glob("*.html")),
            *sorted((destination / "revisions").glob("*.html")),
        ]
        assert len(documents) > 1, route
        canonical = f'<link rel="canonical" href="{page_root}/" data-lf-runtime>'
        for document in documents:
            html = document.read_text(encoding="utf-8")
            head = html[: html.index("</head>")]
            assert canonical in head, document
            assert f'content="{site_build.SITE_ORIGIN}{page["image"]}"' in head, (
                document
            )
            # A card falls back to the page's own words, so a stale title here is
            # what a shared link would show.
            assert (
                f'property="og:title" content="{html_module.escape(page["title"])}"'
                in head
            ), document
        if page["kind"] == "product":
            # Whoever draws the card draws it at 1.91:1 and centre-crops whatever it
            # is given, so a picture of another shape arrives with a band off the top
            # and the bottom. The product shot lost its chrome that way: the version
            # control, the approval, the thread count, every part of the picture that
            # says the page is live.
            with Image.open(assets / page["image"].lstrip("/")) as card:
                assert card.size == (1200, 630), route


def test_the_edge_shell_is_the_document_and_runtime_the_leaf_server_serves(
    site, hosted
):
    """Materialization reuses Leaf's delivery transforms rather than approximating them.

    Every address a page answers is checked, not just its root: the shell and the
    server compose the same transforms, and a route either of them composes
    differently is one where a user's page and a crawler's page part company.
    """
    assets = site_build.asset_site(site)
    manifest = json.loads((assets / site_build.SITE_MANIFEST).read_text())
    asset_root = manifest["pages"]["/examples/triage-board"]["assets"]
    board = assets / "examples" / "triage-board"
    historical = [
        document.relative_to(assets).as_posix()
        for directory in ("versions", "revisions")
        for document in sorted((board / directory).glob("*.html"))
    ]
    assert historical, "the example publishes no version or revision documents"
    revision = active_revision_directory(site / "examples" / "triage-board")
    for route, relative in (
        ("/", "index.html"),
        ("/examples/triage-board/", "examples/triage-board/index.html"),
        (
            f"{asset_root}/{revision}/runtime/check-api.js",
            f"examples/triage-board/{revision}/runtime/check-api.js",
        ),
        *((f"/{relative}", relative) for relative in historical),
    ):
        try:
            with urllib.request.urlopen(f"{hosted}{route}") as response:
                served = response.read()
        except urllib.error.HTTPError as error:
            pytest.fail(f"{route}: {error}")
        materialized = (assets / relative).read_bytes()
        if relative.endswith(".html"):
            served = re.sub(
                rb'data-lf-server="[^"]+"', b'data-lf-server="published"', served
            )
        assert materialized == served, route


def test_every_published_page_keeps_its_canonical_page_record(site):
    """Static routes are derived beside, rather than replacing, Leaf's page record."""
    for source in published_pages():
        page_dir = site / "examples" / source.stem
        versions = example_versions(source)
        events = read_events(page_dir)
        mappings = files_model.version_revisions(events)
        operations = data_operations(source)
        contracts = data_model.read_contracts(page_dir)

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
            # The seed is history, so the page acknowledges all of it.
            receipt = next(event for event in events if event["kind"] == "receipt")
            assert acknowledged(events) == receipt["seq"] - 1
        else:
            assert acknowledged(events) == 0
        assert set(contracts) == {operation["source"] for operation in operations}
        for operation in operations:
            stored = data_model.source_file(page_dir, operation["source"])
            assert json.loads(stored.read_text())["value"] == operation["value"]

        for name in ("events.jsonl", schema_model.LAYER_FILE):
            assert (page_dir / name).is_file(), f"{source.name}: no {name}"
        # The layer and runtime are the serving Leaf's, which the release publishes
        # beside each revision rather than the page holding them
        # (`runtime_selection`).
        for sub in ("media", "revisions"):
            assert list((page_dir / sub).iterdir()), f"{source.name}: {sub}/ is empty"
        assert declared(page_dir)["state"] == "idle"
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
    page = open_page(browser, url)
    expect_showing(page, 2)
    current = page.evaluate("() => fetch('api/state').then(r => r.json())")
    assert current["active"]["revision"] == mappings[2]
    assert current["active"]["version"] == 2
    assert current["active"]["url"].startswith(
        f"/examples/{name}/revisions/r{mappings[2]}-"
    )
    assert current["active"]["label"] == "v2"
    assert current["versions"] == versions

    expect(panel_menu(page, "versions").locator(".lf-fp-version")).to_have_count(2)
    compare_with(page, 1)
    expect(page.locator("main .lf-ins-block")).to_have_count(5)

    panel_menu(page, "versions").locator(
        ".lf-fp-version:not([data-current]) > .lf-fp-item"
    ).click()
    page.wait_for_url(
        re.compile(r"/examples/log-retention/versions/v1\.html(?:\?pin=)?$")
    )
    wait_until_ready(page)

    expect_showing(page, 1)
    expect(page.locator("#ret-cost-keep")).to_have_count(0)
    markup = page.evaluate(
        "() => fetch('../versions/v1.html').then(response => response.text())"
    )
    assert '<meta name="lf-version" content="1" data-lf-runtime>' in markup
    assert (
        f'<meta name="lf-revision" content="{mappings[1]}" data-lf-runtime>' in markup
    )
    pinned = page.evaluate("() => fetch('../api/state').then(r => r.json())")
    assert pinned["versions"] == versions


def test_a_nested_page_keeps_one_draft_across_its_version_addresses(
    served_example, browser
):
    """A published example lives under its own directory, and its live root and each
    version address are one page to what the tab keeps: a comment typed on one is the
    draft on the other."""
    _, url = served_example("log-retention")
    page = open_page(browser, url)
    write(page_comment(page), "Kept across addresses")

    opened(page, f"{url}versions/v1.html")
    expect_showing(page, 1)
    expect(page_comment(page)).to_have_js_property("value", "Kept across addresses")


def test_the_published_notification_example_runs_its_authored_module(
    served_example, browser
):
    _, url = served_example("notification-playground")
    page = open_page(browser, url)
    pressure = page.get_by_role("slider", name="Concurrent release events")
    expect(pressure).to_have_js_property("value", "2")

    pressure.press("ArrowRight")
    pressure.press("ArrowRight")

    expect(page.locator(".notification-demo-card-banner")).to_have_count(4)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(4)


def test_published_visual_evidence_loads_from_its_page(served_example, browser):
    """Typed media paths resolve under the same page as authored media."""
    _, url = served_example("visual-review-gallery")
    page = open_page(browser, url)
    review = page.locator("#visual-review-run")
    for case_id in ("open-mobile-package-catalog", "keep-mobile-destinations"):
        review.locator(
            f'.lf-vr-case-button[aria-controls="visual-review-run-{case_id}"]'
        ).click()
        comparison = review.locator(".lf-vr-case:not([hidden]) lf-shot")
        expect(comparison).to_be_visible()
        images = comparison.locator("img")
        expect(images).to_have_count(2)
        for image in images.all():
            expect(image).to_have_js_property("complete", True)
            assert image.evaluate("image => image.naturalWidth") > 0


def test_a_replaced_private_server_keeps_the_active_tab(served_example, browser):
    """Durable content keeps the current document when its serving process changes."""
    _, url = served_example("triage-board")
    page = open_page(browser, url)
    page.evaluate("window.__originalDocument = true")
    reading = page.locator("body").get_attribute("data-lf-reading")
    replaced = []

    def replacement(route):
        answer = route.fetch()
        if replaced:
            route.fulfill(response=answer)
            return
        replaced.append(answer.text())
        route.fulfill(
            response=answer,
            headers={
                **answer.headers,
                "leaf-session": "active",
                "leaf-server": "replacement-private-server",
            },
        )

    page.route("**/api/news", replacement)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/news")
            and response.headers.get("leaf-server") == "replacement-private-server"
        )
    ) as response:
        pass
    assert response.value.text() == reading
    # The next poll starts after the runtime admitted the replacement response.
    with page.expect_request("**/api/news"):
        pass
    page.unroute("**/api/news", replacement)
    assert replaced == [reading]
    wait_until_ready(page)
    assert page.evaluate("window.__originalDocument === true")


def test_a_document_on_a_dead_release_asks_for_one_replacement(served_example, browser):
    """A document whose release is gone asks for a newer one once, not in a loop.

    Nothing this document names can load once its release is gone, so recovery has to
    go and get another document. Where what answers is a copy of the same one — an edge
    or intermediary cache, a user offline — asking again lands on that same copy, and
    the page asked for it as fast as the network could carry it. The count is the
    assertion: one replacement, then the probe's own cadence.
    """
    _, url = served_example("triage-board")
    page = browser.new_page()
    documents = []
    # The probe rounds the replacement document makes. Each one that answers 404 is a
    # round that would ask for another document if recovery looped.
    rounds = []

    def answer(route):
        request = route.request
        if request.resource_type == "document":
            documents.append(request.url)
            route.continue_()
        else:
            if len(documents) > 1 and "/registry.json" in request.url:
                rounds.append(request.url)
            route.fulfill(status=404, content_type="text/plain", body="")

    # The entry module and the probe are the release's own two addresses: one says the
    # page cannot start, the other says the release it belongs to is no longer served.
    page.route("**/leaf.js", answer)
    page.route("**/registry.json", answer)
    page.route(url, answer)
    page.route(url + "?*", answer)
    page.goto(url, wait_until="load")
    banner = page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    expect(banner).to_be_visible()
    holding(page, rounds, 3, "three probe rounds from the replacement document")
    assert len(documents) == 2, documents
    assert "_leaf-recovered" in documents[1], documents
    # The mark is the runtime's own and does not stay in front of the user.
    assert "_leaf-recovered" not in page.evaluate("location.href")
    expect(banner).to_be_visible()
    # The failed-release probe keeps requesting while the page is open. End that
    # source of deliberate 404s before accounting for its browser reports.
    page.close()
    consume_browser_errors(
        page,
        lambda problem: (
            is_problem(problem, http_error_console(404))
            and urlsplit(problem.values["url"]).path.endswith(
                ("/leaf.js", "/registry.json")
            )
        ),
    )


def test_a_page_that_starts_after_a_fault_takes_its_notice_back(
    served_example, browser
):
    """A fault the page recovers from leaves the user a working page, not a notice.

    The supervisor's notice says the page has not started. A page that loses something
    on the way up and presents anyway has started, so a user who is using the page
    would otherwise be reading that Leaf could not start, over a probe request a second
    that no answer ends. The record keeps the fault instead.
    """
    _, url = served_example("triage-board")
    page = browser.new_page()
    # One uncaught error before presentation, which is every startup fault this
    # supervisor watches for that the page can still come up without.
    page.add_init_script("setTimeout(() => { throw new Error('planted fault'); }, 50);")
    probes = []
    page.on("request", lambda request: probes.append(request.url))

    page.goto(url, wait_until="load")
    notice = page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(notice).to_have_count(0)
    expect(page.locator(".lf-fp-on-user")).to_be_visible()

    # The probe stops with it: a page that started has nothing left to ask the source.
    before = sum("registry.json" in probe for probe in probes)
    page.wait_for_timeout(3000)
    assert sum("registry.json" in probe for probe in probes) == before
    consume_browser_errors(page, "planted fault")


def test_a_probe_in_flight_leaves_a_page_that_started_alone(served_example, browser):
    """The round that was already asking when the page came up does not navigate it.

    A probe round begins at the fault and ends whenever the source answers, which can
    be after the page has upgraded. By then the user is using the page, so what that
    round learned is no longer worth a navigation: it would take a working page out
    from under them.

    Both halves are planted, because the two the page would produce cannot be ordered
    against each other here: the supervisor's probe and the runtime's own widget read
    are the same address, so holding one holds the other and nothing presents. The
    fault and `data-lf-upgraded` are the supervisor's two inputs, and the test lands
    the second one while its first round is still asking.
    """
    _, url = served_example("triage-board")
    page = browser.new_page()
    page.add_init_script(
        """
        setTimeout(() => { throw new Error('planted fault'); }, 10);
        setTimeout(() => document.body?.setAttribute('data-lf-upgraded', '1'), 600);
        """
    )
    documents = []
    page.on(
        "request",
        lambda request: (
            documents.append(request.url)
            if request.resource_type == "document"
            else None
        ),
    )
    held = []

    def hold_the_first_round(route):
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route("**/registry.json", hold_the_first_round)
    page.goto(url, wait_until="domcontentloaded")
    holding(page, held, 1, "the supervisor's first probe round")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    # Answered once the page has upgraded, as a release that has rolled past: the
    # answer that would otherwise replace the document.
    held[0].fulfill(status=404, content_type="text/plain", body="")
    answered = held[0].request.response()
    assert answered and answered.status == 404, "the held round's answer never landed"
    # The round acts on its answer as it lands, so a replacement would be a navigation
    # starting now. Nothing states that the round declined one; this is the absence.
    page.wait_for_timeout(2000)

    assert len(documents) == 1, documents
    expect(
        page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    ).to_have_count(0)
    take_browser_errors(page)


def test_session_activation_reaches_other_tabs(served_example, browser):
    """Activation reaches this page's tabs, including a pinned revision, only."""
    page_dir, url = served_example("triage-board")
    _, other_url = served_example("heat-loss")
    context = browser.new_context()
    leader, follower, other_page, other_release = [context.new_page() for _ in range(4)]
    pages = (leader, follower, other_page, other_release)
    # Capture the native channel to send an ordered delivery barrier after activation.
    # Each recipient handles that marker after the runtime handles the earlier message.
    context.add_init_script(
        """window.BroadcastChannel = class extends BroadcastChannel {
          constructor(name) {
            super(name);
            if (name.startsWith('leaf-session') && !window.__sessionChannel)
              window.__sessionChannel = this;
          }
        };"""
    )
    try:
        different_release = "f" * 64

        def passive_session(route):
            response = route.fetch()
            headers = {**response.headers, "leaf-session": "passive"}
            if route.request.frame.page == other_release:
                headers["leaf-release"] = different_release
            route.fulfill(response=response, headers=headers)

        def different_document(route):
            response = route.fetch()
            body = re.sub(
                r'data-lf-release="[^"]+"',
                f'data-lf-release="{different_release}"',
                response.text(),
            )
            assert body != response.text(), "the release control changed no declaration"
            route.fulfill(response=response, body=body)

        other_release.route(f"{url}?other-release", different_document)
        revision = files_model.latest_revision(page_dir)
        assert revision is not None
        version_url = f"{url}versions/v{revision}.html"
        for page, address in zip(
            pages, (url, version_url, other_url, f"{url}?other-release")
        ):
            page.route("**/api/state*", passive_session)
            page.route("**/registry.json", passive_session)
            page.route("**/api/news", passive_session)
            page.goto(address, wait_until="load")
            wait_until_ready(page)
            page.evaluate(
                """() => {
                  window.__leafActivated = 0;
                  window.__activationBarrier = false;
                  document.addEventListener('lf-session-active', () => window.__leafActivated++);
                  window.__sessionChannel.addEventListener('message', event => {
                    if (event.data.activationBarrier) window.__activationBarrier = true;
                  });
                }"""
            )
        names = [page.evaluate("window.__sessionChannel.name") for page in pages[1:]]
        leader.evaluate(
            """async names => {
              const client = await window.__lfClientApi();
              client.admitResponse(new Response(null, {headers: {'Leaf-Session': 'active'}}));
              for (const name of new Set(names)) {
                const sender = window.__sessionChannel.name === name
                  ? window.__sessionChannel : new BroadcastChannel(name);
                sender.postMessage({activationBarrier: true});
                if (sender !== window.__sessionChannel) sender.close();
              }
            }""",
            names,
        )
        for page in pages[1:]:
            page.wait_for_function("window.__activationBarrier")
        assert [page.evaluate("window.__leafActivated") for page in pages] == [
            1,
            1,
            0,
            0,
        ]
        assert [
            page.evaluate(
                "async () => (await window.__lfClientApi()).sessionIsActive()"
            )
            for page in pages
        ] == [True, True, False, False]
    finally:
        for page in pages:
            page.unroute_all(behavior="ignoreErrors")


def test_freshness_checks_preserve_session_activation_without_rebroadcasting(
    served_example, browser
):
    """Session activation wakes peers once; subsequent server changes stay quiet."""
    _, url = served_example("triage-board")
    page = browser.new_page()
    page.add_init_script(
        """const post = BroadcastChannel.prototype.postMessage;
        window.__sessionBroadcasts = [];
        BroadcastChannel.prototype.postMessage = function(value) {
          if (this.name.startsWith('leaf-session:')) window.__sessionBroadcasts.push(value);
          return post.call(this,value);
        };"""
    )

    def passive(route):
        answer = route.fetch()
        route.fulfill(
            response=answer,
            headers={**answer.headers, "leaf-session": "passive"},
        )

    looks = []

    def active(route):
        answer = route.fetch()
        looks.append(answer)
        route.fulfill(
            response=answer,
            headers={
                **answer.headers,
                "leaf-session": "active",
                "leaf-server": "private-server",
            },
        )

    page.route("**/api/state*", passive)
    page.route("**/registry.json", passive)
    page.route("**/api/news", active)
    page.goto(url, wait_until="load")
    wait_until_ready(page)
    # An active error envelope still establishes the session.
    # Later freshness responses may come from another serving process, while the
    # same durable record and browser session continue.
    page.evaluate(
        """async()=>{
          const client=await window.__lfClientApi();
          window.__activations=0;
          document.addEventListener('lf-session-active',()=>window.__activations++);
          client.admitResponse(new Response('', {status:503, headers:{
            'Leaf-Session':'active'
          }}));
        }"""
    )
    page.wait_for_function("window.__sessionBroadcasts.length===1")
    for _ in range(4):
        with page.expect_response("**/api/news"):
            pass
    assert len(looks) >= 4
    assert page.evaluate("window.__activations") == 1
    assert page.evaluate("window.__sessionBroadcasts") == [{"active": True}]
    assert page.evaluate("async () => (await window.__lfClientApi()).sessionIsActive()")


def test_every_product_route_is_a_live_leaf_page(site, hosted, browser):
    """Each product route runs the canonical runtime and exposes its page state. It
    takes its paper from the theme in both schemes, and nothing scrolls sideways at
    390px: the nav wraps, the screenshots scale, and a command too long for the
    column scrolls inside its own block, as the architecture diagram fits its box."""
    names = [source.name for source in site_build.product_sources()]
    page = browser.new_page()
    failed = []
    page.on(
        "response",
        lambda response: (
            failed.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None
        ),
    )
    paper = "getComputedStyle(document.body).backgroundColor"
    for name in names:
        page.set_viewport_size({"width": 1200, "height": 900})
        page.goto(product_url(hosted, name), wait_until="load")
        wait_until_ready(page)
        assert page.evaluate("document.compatMode") == "CSS1Compat", name
        source = (DOCS / name).read_text(encoding="utf-8")
        expected_title = SourceDocument(source).authoring.title.strip()
        assert expected_title
        assert page.title() == expected_title, name
        expect(page.locator("h1")).to_have_text(heading(source))
        expect(page.locator(".lf-chrome")).to_have_count(1)
        expect(page.locator("script[data-lf-server]")).to_have_count(1)
        expect(page.locator('link[rel="stylesheet"]')).to_have_count(1)
        expect(page.locator("main > .sitenote")).to_have_count(0)
        if "<lf-toc" in source:
            assert page.locator("lf-toc a").count() > 0, (
                f"{name}: the table of contents has no links"
            )
        state = page.evaluate("() => fetch('api/state').then(r => r.json())")
        assert state["publication"] == {
            "kind": "product",
            "agent": "Agent",
            "install_url": "/#install",
        }
        if name == "how-it-works.html":
            # The package can use the page margins beyond its prose-width figure.
            # Its own scrollport, rather than that wrapper, bounds the drawing.
            diagram = page.locator("#agent-browser-architecture")
            expect(diagram).to_be_visible()
            width = diagram.evaluate(
                "element => ({client: element.clientWidth, scroll: element.scrollWidth})"
            )
            assert width["scroll"] == width["client"]
        for scheme in ("dark", "light"):
            page.emulate_media(color_scheme=scheme)
            assert page.evaluate(paper) == PAPER[scheme], (name, scheme)
        page.set_viewport_size(PHONE)
        wait_until_ready(page)
        overflow = root_overflow(page)
        assert overflow == 0, f"{name} scrolls {overflow}px sideways on a phone"
        assert not failed, f"{name}: {failed[:3]}"


@pytest.fixture(name="staged_site")
def staged_site(site, tmp_path):
    """The module's built site, copied for one test to break files in.

    `build` links the vendored layer into every page it publishes rather than
    writing it again, so the site is 18,054 files and 65M on disk. A plain
    `copytree` copies bytes and breaks every one of those links, so each copy
    measured 398M. Sharing the layer the way `build` does, and the way a lent page
    shares it, brings that to 84M. It buys nothing in time — the two take 3.5s and
    3.9s, because the cost is the directory entry rather than the bytes — and
    everything outside the layer is still copied, so a test rewrites the file it is
    here to break without that write reaching the build the rest of the module reads.
    """
    staged = tmp_path / "staged"

    def share_layer(source, target):
        relative = Path(source).relative_to(site).parts
        if LENT_LINKED_DIRS.isdisjoint(relative):
            shutil.copy2(source, target)
        else:
            os.link(source, target)

    shutil.copytree(site, staged, copy_function=share_layer)
    return staged


def test_the_public_catalog_paints_in_its_final_position_before_leaf_loads(
    hosted, browser
):
    """The catalog's position and width are set before the runtime loads.

    The map-only sidebar has no vertical room before or after the runtime moves
    its contents into the margin, so mounting Leaf does not move the cards.
    """
    boot = []
    page = browser.new_page(viewport={"width": 1724, "height": 1036})
    page.route("**/examples/revisions/*/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/examples/revisions/*/leaf.js"):
            page.goto(f"{hosted}/examples/", wait_until="commit")
        displayed(page)
        expect(page.locator("h1")).to_be_visible()
        assert boot, "the positive control did not hold the catalog boot module"
        catalog = page.locator(".example-catalog").first
        initial = page.locator("main").bounding_box()
        initial_catalog = catalog.bounding_box()

        boot.pop().continue_()
        wait_until_ready(page)
        final = page.locator("main").bounding_box()
        assert {key: final[key] for key in ("x", "y", "width")} == pytest.approx(
            {key: initial[key] for key in ("x", "y", "width")}, abs=1
        )
        final_catalog = catalog.bounding_box()
        assert {
            key: final_catalog[key] for key in ("x", "y", "width")
        } == pytest.approx(
            {key: initial_catalog[key] for key in ("x", "y", "width")}, abs=1
        )
        assert initial_catalog["width"] > page.evaluate(
            "() => parseFloat(getComputedStyle(document.documentElement)"
            ".getPropertyValue('--col'))"
        ), "the catalog painted at the prose measure and widened once leaf.js resolved"
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_the_public_catalog_is_a_visual_index_of_full_page_routes(
    site, hosted, browser
):
    """Curated examples have previews; unlisted examples retain working routes.

    The absence checks are held by positive populations: catalog entries, loaded
    images, and the independently derived authored files. A vanished catalog
    cannot pass merely because it also contains no iframe or tab widget.
    """
    expected = {source.stem for source in catalog_sources()}
    authored = {source.stem for source in authored_examples()}
    assert authored - expected, "the fixture has no unlisted example route to exercise"
    previews = pinned_assets() / "examples"
    assert {path.name for path in previews.glob("example-*.jpg")} >= {
        f"example-{stem}.jpg" for stem in expected
    }

    page = browser.new_page()
    page.goto(f"{hosted}/examples/", wait_until="load")
    wait_until_ready(page)
    expect(page.locator(".lf-chrome")).to_have_count(1)
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
        assert (
            Path(urlsplit(pair["image"]).path).name
            == Path(media_url(previews / f"example-{stem}.jpg")).name
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
    published = {path.name for path in (site / "examples").iterdir() if path.is_dir()}
    assert published == authored | {source.stem for source in DEVELOPER_PAGES}
    assert page.evaluate(
        "() => Boolean(document.querySelector('#pages')"
        ".compareDocumentPosition(document.querySelector('#developer-galleries'))"
        " & Node.DOCUMENT_POSITION_FOLLOWING)"
    )
    product_gallery = developer_galleries.locator("#product-gallery")
    expect(product_gallery).to_contain_text("Core product gallery")
    expect(product_gallery).to_contain_text("core interactions to try live")
    expect(product_gallery).to_have_attribute("href", "/examples/feature-gallery/")
    threads_gallery = developer_galleries.locator("#thread-panel-gallery")
    expect(threads_gallery).to_contain_text("Four live panel views")
    expect(threads_gallery).to_have_attribute("href", "/examples/thread-panel-gallery/")


def test_a_sample_keeps_ephemeral_storage_and_presents_uploaded_media(serve, browser):
    """Opaque children retain working state and display authenticated uploaded bytes."""
    source = """<!doctype html><html><head><title>Sample state</title></head><body><main>
      <lf-sample id="practice" label="practice page">
        <template id="practice-page" data-sample><p id="copy">Practice here.</p></template>
      </lf-sample>
    </main></body></html>"""
    page = open_page(browser, serve(source))
    sample = page.locator("#practice")
    frame = sample.locator("iframe")
    child = frame.content_frame.locator("html")
    assert frame.evaluate("frame => frame.contentDocument === null")
    result = child.evaluate(
        """async () => {
          const {tabStore, draftStore, userStore} = await window.__lfCheckApi();
          const {uploadMedia} = await window.__lfClientApi();
          const {scopedMediaUrl} = await window.__lfWidgetApi();
          const denied = ['localStorage', 'sessionStorage'].every(name => {
            try { window[name]; return false; } catch { return true; }
          });
          const retained = [tabStore, draftStore, userStore].every((store, index) => {
            const value = `child-${index}`;
            return store.set('isolation-test', value)
              && store.get('isolation-test') === value
              && store.keys().includes('isolation-test');
          });
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 2;
          canvas.getContext('2d').fillRect(0, 0, 2, 2);
          const bytes = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
          const path = await uploadMedia(new File([bytes], 'practice.png', {type: bytes.type}));
          const image = document.createElement('img');
          image.src = scopedMediaUrl(path);
          document.body.append(image);
          await image.decode();
          return {denied, retained, path, url: image.src,
            shown: image.naturalWidth === 2 && image.naturalHeight === 2};
        }"""
    )
    assert result["denied"] and result["retained"] and result["shown"]
    assert result["path"].startswith("/media/")
    assert result["url"].startswith(f"{sample_address(frame)}media/")
    sample.get_by_role("button", name="Reset", exact=True).click()
    sample.evaluate("async sample => { await sample.ready; }")
    assert child.evaluate(
        """async () => {
          const {tabStore, draftStore, userStore} = await window.__lfCheckApi();
          return [tabStore, draftStore, userStore].every(store => store.get('isolation-test') === null);
        }"""
    )


def test_every_published_page_stands_as_a_live_page(served_example, browser):
    """Every artifact starts through Leaf's own document and state boundaries.

    A published workspace owns main and keeps its bounded reading regions: the page
    does not scroll, and each region scrolls on its own, whether that is a pane's body
    or the workspace's body itself, as where a side-list queue is the body."""
    framed = set(framed_root_examples())
    pages = published_pages()
    _, url = served_example(pages[0].stem)
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 900})
    for source in pages:
        if source != pages[0]:
            _, url = served_example(source.stem)
            opened(page, url)
        newest = len(example_versions(source))
        expect_showing(page, newest)
        expect(page.locator(".lf-fp-leaf")).to_have_attribute(
            "aria-label", "Page menu · Ready — comment to revise this copy"
        )
        if source == FEATURE_GALLERY:
            samples = page.locator("#bg-interactions lf-sample")
            expect(samples).to_have_count(3)
            for sample in samples.all():
                sample.evaluate("async sample => { await sample.ready; }")
        if source.stem in framed:
            framed.remove(source.stem)
            expect(page.locator("body > main.layout-workspace")).to_have_count(1)
            expect(page.locator("body > main .sitenote")).to_have_count(0)
            page.wait_for_function(WORKSPACE_REGIONS_SCROLL_ALONE)
    assert not framed, f"framed examples the sweep never opened: {framed}"


WORKSPACE_REGIONS_SCROLL_ALONE = """() => {
  const page = document.documentElement;
  const main = document.querySelector('body > main.layout-workspace');
  const pane = '[data-lf-reading-role="pane"]';
  const bodyOf = (box) =>
    [...box.children].find(child => !child.matches('header, footer'));
  const regions = [
    ...[...main.children].filter(
      child => !child.matches('header, footer') && !child.matches(pane)),
    ...[...main.querySelectorAll(pane)].map(bodyOf),
  ];
  return page.scrollHeight === page.clientHeight && regions.length > 0
    && regions.every(region => getComputedStyle(region).overflowY === 'auto');
}"""


def test_an_example_paints_while_every_stage_of_site_startup_is_held(
    served_example, browser
):
    """Authored HTML paints before JavaScript or server state is ready.

    Holding /leaf.js proves widget upgrade cannot be what made the document visible or
    placed its shell. The waiting pseudo-element's computed content proves the loading
    sheet does not exist, without waiting for an animation threshold. Once JavaScript
    starts, holding /api/state proves the data-bound diff waits for the backend's
    canonical projection and that presentation keeps the initial shell in place.
    """
    boot = []
    state = []
    _, url = served_example("pr-walkthrough")
    page = browser.new_page(viewport={"width": 1724, "height": 900})
    page.route("**/leaf.js", lambda route: boot.append(route))
    page.route("**/api/state*", lambda route: state.append(route))

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        displayed(page)
        expect(page.locator("h1")).to_have_text(example_title("pr-walkthrough"))
        expect(page.locator("h1")).to_be_visible()

        assert boot, "the positive control did not hold the site boot module"
        expect(page.locator("body > main")).to_have_css("pointer-events", "auto")
        initial_shell = {
            key: page.locator("body > main").bounding_box()[key]
            for key in ("x", "y", "width")
        }
        assert (
            page.evaluate("() => getComputedStyle(document.body, '::after').content")
            == "none"
        ), "the waiting sheet painted before the site boot module arrived"

        with page.expect_request("**/api/state*"):
            boot.pop().continue_()

        assert page.locator("body").get_attribute("data-lf-presented") is None
        assert state, "the canonical state request was not still in flight"
        mounted_shell = {
            key: page.locator("body > main").bounding_box()[key]
            for key in initial_shell
        }
        assert mounted_shell == pytest.approx(initial_shell, abs=1), (
            f"mounting Leaf moved the initial shell from {initial_shell} to "
            f"{mounted_shell}"
        )
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
        wait_until_ready(page)
        presented_shell = {
            key: page.locator("body > main").bounding_box()[key]
            for key in initial_shell
        }
        assert presented_shell == pytest.approx(initial_shell, abs=1), (
            f"presenting Leaf moved the initial shell from {initial_shell} to "
            f"{presented_shell}"
        )
    finally:
        for route in boot:
            route.continue_()
        for route in state:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_a_published_example_has_no_agent_claim(served_example, browser):
    """A finished public page claims neither an agent nor an active session, and its
    backend answers the exact projection path the runtime asks for."""
    page_dir, url = served_example("triage-board")
    page = open_page(browser, url)
    state_head = panel_menu(page).locator(".lf-fp-state")
    expect(state_head).to_contain_text(
        "This is an example on the Leaf website, and this copy is private to this browser."
    )
    assert state_head.locator("a").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    ) == ["/examples/", "/#install"]
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(".sitenote")).to_have_count(0)
    # Unclaimed, the copy's agent is still on call: a comment starts it.
    assert page.locator(".lf-fp-leaf .lf-dot").evaluate(
        "dot => [...dot.classList]"
    ) == ["lf-dot", "listening"]
    state = page.evaluate("() => fetch('api/state').then(r => r.json())")
    assert state["publication"] == {
        "kind": "example",
        "agent": "Agent",
        "install_url": "/#install",
    }
    assert state["browser"]["todos"] == []
    assert state["session_alive"] is None
    assert not state["listening"]
    assert not (page_dir / "service.json").exists()

    # The page backend answers the exact projection path the runtime asks for.
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


def test_a_shipped_log_opens_its_example_on_its_thread(served_example, browser):
    """An example that ships a log arrives mid-thread through the real projection.

    The thread is the one thing no markup describes, so a copy of the markup could never
    carry one however it was written. Leaf reads the complete page directory's log into
    the runtime's first state answer, so the panel never renders empty and then fills in.

    The anchor is the half that rots quietly: the quote is captured against the file, and
    a rewritten sentence leaves it resolving to nothing and the thread left detached,
    with no error anywhere."""
    _, url = served_example("ship-review")
    page = open_page(browser, url)
    source = EXAMPLES / "ship-review.html"
    events = _parse_events(source.with_suffix(".jsonl").read_bytes())
    threads = [
        thread
        for thread in build_threads(
            events,
            enclosing_ids(SourceDocument(source.read_text(encoding="utf-8"))),
        ).values()
        if not bare_reaction(thread)
    ]
    opened = sum(not thread["resolved"] for thread in threads)
    resolved = len(threads) - opened
    assert opened and resolved, "the shipped seed must cover both thread states"
    open_threads(page)
    expect(panel_tab(page, "Threads").locator(".lf-fp-count")).to_have_text(str(opened))
    expect(page.locator(".lf-fp-ended ~ .lf-fp-thread[data-resolved]")).to_have_count(
        resolved
    )
    # Named rather than taken first: the assertion follows the shipped objection,
    # independent of where a later seed might place another thread.
    row = page.locator(".lf-fp-thread").filter(
        has_text="One reconnect in forty is worse"
    )
    expect(row).to_have_count(1)
    row.click()
    thread = page.locator(PANEL_THREAD)
    expect(thread.locator(".lf-fp-quote")).to_have_text("“One reconnect in about 40”")
    assert thread.locator(".lf-fp-quote.detached").count() == 0, (
        "the shipped anchor found nothing on the page it was captured from"
    )
    # Painted, not merely resolved: the mark is what puts the user at the passage.
    assert "lf-mark" in page.evaluate("() => [...CSS.highlights.keys()]")
    # The question Claude asks in that thread is a widget, upgraded from the
    # same canonical state a user can answer where they are located.
    item = page.locator("#off-slip")
    expect(item).to_be_visible()
    assert item.locator("[data-lf-offer]").count() > 0, (
        "the group renders on the site with nothing to press, so the decision "
        "is a picture of one"
    )


def test_shipped_data_opens_in_its_package_projection(site, served_example, browser):
    """The page backend delivers package data through the live state contract, and
    the page counts every obligation it declares."""
    stored = data_model.source_file(
        site / "examples" / "command-hub", "atlas-worktrees"
    )
    assert (
        json.loads(stored.read_text())["value"]["tree-w-1"]["branch"]
        == "atlas/xml-declarations"
    )

    _, url = served_example("command-hub")
    page = open_page(browser, url)
    snapshot = page.locator('#tree-w-1 [data-lf-datum="tree-w-1"]')
    expect(snapshot).to_have_count(1)
    expect(snapshot).to_contain_text("atlas/xml-declarations")
    expect(
        snapshot.locator("dt", has_text="Tests").locator(
            "xpath=following-sibling::dd[1]"
        )
    ).to_have_text("running")
    # The inventory includes request Decisions beside state obligations.
    expect_obligations_answered(page, "0/5")
    expect(page.locator(".lf-fp-on-user")).to_be_visible()


def test_a_comment_persists_without_inventing_an_agent_reply(served_example, browser):
    """The real backend stores the user's anchored words without impersonating an agent."""
    _, url = served_example("triage-board")
    page = open_page(browser, url)
    # What the page opens with, since an example that ships a log opens with
    # threads already counted. The claim here is that the user's own comment
    # adds one, which is a claim about the gesture rather than about the corpus.
    opened_with = open_count(page)
    box = page.locator("#triage-lede").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 8),
        (box["x"] + box["width"] - 40, box["y"] + box["height"] - 8),
    )
    selected = page.evaluate("getSelection().toString()")
    assert selected.strip()
    # Selection offers the compact field without entering it, so the browser's
    # own selection is still there for a native copy.
    expect(page.locator(".lf-fab-input")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can the migration fix ship first?")
    with sending(page, "the anchored comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    # The thread holding the words just written, rather than whichever is first:
    # an example that ships a log opens with threads already in the panel, and
    # theirs would be first. triage-board ships none today, so `.first` was
    # right by accident and would stop being on the day it does.
    def written():
        open_threads(page)
        page.locator(".lf-fp-thread").filter(
            has_text="Can the migration fix ship first?"
        ).click()
        return page.locator(PANEL_THREAD)

    expect_open_threads(page, opened_with + 1)
    thread = written()
    expect(thread).to_contain_text("Can the migration fix ship first?")
    expect(thread.locator(".lf-fp-quote")).to_contain_text(selected.strip()[:40])
    expect(thread.locator(".lf-msg.agent")).to_have_count(0)
    page.reload(wait_until="load")
    wait_until_ready(page)
    thread = written()
    expect(thread).to_contain_text("Can the migration fix ship first?")
    expect(thread.locator(".lf-fp-quote")).to_contain_text(selected.strip()[:40])
    expect(thread.locator(".lf-msg.agent")).to_have_count(0)


def test_a_published_decision_survives_reload(served_example, browser):
    """A published example uses Leaf's durable log rather than browser-only state."""
    _, url = served_example("heat-loss")
    page = open_page(browser, url)
    decisions = page.locator(".lf-fp-on-user")
    expect_obligations_answered(page, "0/1")
    expect(decisions).to_be_visible()
    chosen = "() => [...document.querySelectorAll('lf-option[chosen]')].map(o => o.id)"
    with sending(page, "the published option pick"):
        page.locator("#heat-opt-floor .lf-pick").click()
    expect(page.locator("#heat-first")).to_have_attribute("data-lf-user-override", "1")
    assert "heat-opt-floor" in page.evaluate(chosen)
    expect_obligations_answered(page, "1/1")
    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_obligations_answered(page, "1/1")
    assert "heat-opt-floor" in page.evaluate(chosen)


def test_what_a_user_leaves_on_one_page_stays_on_it(served_example, browser):
    """Independent page backends do not share their logs or reading positions."""
    _, url = served_example("heat-loss")
    page = open_page(browser, url)
    write(page_comment(page), "Where does this go?")
    page.locator(".lf-fp-field .lf-compose-submit").click()
    # One, and typed: this example ships no log, so the count is the comment
    # just written and nothing else.
    expect_open_threads(page, 1)
    # The page's own scroller (the runtime's `pageScroller`), moved the way a
    # user moves it far enough down that the landmark is worth restoring.
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 1500, behavior: 'instant'})"
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") > 0, (
        "the document did not scroll, so the landmark under test was never written"
    )

    # An example that ships no log of its own, so the count there is the user's
    # own doing or nobody's. Asked of the corpus rather than named, since a page
    # that gains a companion log would otherwise turn this into a test of the seed.
    plain = next(
        p.stem
        for p in authored_examples()
        if p.stem != "heat-loss" and not p.with_suffix(".jsonl").exists()
    )
    _, plain_url = served_example(plain)
    opened(page, plain_url)
    expect_open_threads(page, 0)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == 0, (
        "the second example opened at the offset left on the first"
    )


def test_a_sample_waits_for_slow_contained_page_state(serve, browser):
    """A healthy contained page may present after an arbitrarily slow state read."""
    url = serve("""<!doctype html><html><head><title>Slow sample</title></head><body><main>
      <lf-sample id="practice" label="practice page">
        <template id="practice-page" data-sample><p id="copy">Practice here.</p></template>
      </lf-sample>
    </main></body></html>""")
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    held = []
    held_once = False
    allocation = sample_allocation(page, url, "practice-page")

    def hold_first_contained_state(route):
        nonlocal held_once
        if (
            allocation["url"] is not None
            and route.request.url.startswith(allocation["url"])
            and not held_once
        ):
            held_once = True
            held.append(route)
            return
        route.continue_()

    page.route("**/api/state*", hold_first_contained_state)
    try:
        with page.expect_request(
            lambda request: (
                allocation["url"] is not None
                and request.url.startswith(allocation["url"])
                and "/api/state" in request.url
            )
        ):
            page.goto(url, wait_until="domcontentloaded")
        sample = page.locator("#practice")
        holding(page, held, 1, "the contained page's first state read")
        held.pop().continue_()
        page.wait_for_load_state("load")
        wait_until_ready(page)
        sample.evaluate("async sample => { await sample.ready; }")
        frame = sample.locator("iframe")
        assert not frame.get_attribute("srcdoc")
        contained_document = frame.content_frame.locator("html")
        assert contained_document.evaluate(
            "() => document.doctype?.name === 'html' && Boolean(document.scrollingElement)"
        )
        page.evaluate("sessionStorage.setItem('lf-view', 'outer reading')")
        storage = contained_document.evaluate(
            """async () => {
                const {readApplication} = await window.__lfCheckApi();
                const {PAGE_SCOPE, tabStore, draftStore, userStore} =
                    await window.__lfCheckApi();
                for (const [name, store] of Object.entries({tabStore, draftStore, userStore})) {
                    if (!store.set('isolation-test', name) || store.get('isolation-test') !== name)
                        throw new Error(`${name} did not retain sample working state`);
                    if (!store.keys().includes('isolation-test'))
                        throw new Error(`${name} did not enumerate its retained state`);
                    store.set('isolation-test', null);
                    if (store.get('isolation-test') !== null)
                        throw new Error(`${name} did not clear its retained state`);
                }
                return {liveRoot: readApplication().document.live, pageScope: PAGE_SCOPE};
            }"""
        )
        assert storage["liveRoot"] is True
        assert "/api/samples/" in storage["pageScope"]
        interaction_url = f"{sample_address(frame)}api/interaction"
        with page.expect_response(
            lambda response: (
                response.url == interaction_url
                and any(
                    entry["type"] == "pagehide"
                    for entry in response.request.post_data_json["entries"]
                )
            )
        ) as departure:
            contained_document.evaluate(
                "dispatchEvent(new PageTransitionEvent('pagehide'))"
            )
        assert departure.value.ok
        assert page.evaluate("sessionStorage.getItem('lf-view')") == "outer reading"
        assert (
            page.evaluate(
                "scope => sessionStorage.getItem(scope + 'lf-view')",
                storage["pageScope"],
            )
            is None
        )
    finally:
        for route in held:
            route.abort()
