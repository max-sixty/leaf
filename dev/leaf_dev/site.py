"""Assemble the published site (https://leaf.page/) into .tmp/site.

Every product document under `docs/` is a Leaf source. The build publishes each one as a
complete page directory, alongside the worked examples. The Worker serves the
build-generated initial projection at the edge, then gives an interacting browser a
private copy through Leaf's canonical Python server. The catalog previews and the
product card come from the max-sixty/leaf-assets revision pinned in `leaf-assets.json`.

The worked examples and developer package galleries become complete Leaf page directories
under examples/<name>/. The same preparation path that serves a local fixture vendors
each page's selected layer, stamps its authored versions, applies its companion event
log and data, and closes the finished page without claiming it for an agent. A second,
derived tree contains the immutable live shell Cloudflare serves before the canonical
server answers its API requests.

A dead link is the failure a static host cannot report, so the build resolves every
local href and src it wrote and refuses a site holding one that names no file.

The build also writes what a crawler reads: `robots.txt`, a `sitemap.xml` of the clean
routes, and each page's link card. A page's title and description are authored in its
own source, and the build refuses a page missing either. The rest of the card comes from
`site_metadata` in `leaf_website` (`worker/`). Each page's card image is named in the manifest:
the demo's `session-card.png` for a product page and the catalog preview for an example.

    uv run leaf-dev site

`npm run dev --prefix worker` builds and then serves the result through `wrangler dev`.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from functools import partial
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import click
from leaf.files import latest_revision, list_revisions
from leaf.live_shell import write_live_shell
from leaf.media import media_name
from leaf.revision_delivery import DeliveryAddress, rebase_document
from leaf.schema import (
    BROWSER_DIRS,
    MEDIA_DIR,
    SESSION_ROUTE_DIRS,
    VENDORED_FILES,
)
from leaf.structure import FRAME_ANCESTORS_CSP, SourceDocument
from leaf_website import SITE_MANIFEST, SITE_ORIGIN, initial_state, site_metadata

from leaf_dev import LEAF_COMMAND, ROOT
from leaf_dev.example_data import catalog_sources
from leaf_dev.harness import environment
from leaf_dev.leaf_assets import pinned_assets
from leaf_dev.page_fixtures import (
    package_selection_args,
    prepare_page,
    read_fixture,
)

DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
INTERNAL_EXAMPLES = {"corpus"}
DEVELOPER_PAGES = tuple(sorted((EXAMPLES / "developer").glob("*.html")))
OUT = ROOT / ".tmp" / "site"
BUNDLE_RUNTIME = ROOT / "worker" / "bundle-runtime.mjs"

PRODUCT_ROUTES = {
    "index.html": "/",
    "examples.html": "/examples/",
    "how-it-works.html": "/how-it-works/",
    "extending.html": "/extending/",
    "registry.html": "/registry/",
    "event-log.html": "/event-log/",
}
SITE_PACKAGE = "./docs/package"
# The card a link to a product page unfurls into, shot at the 1.91:1 an unfurler draws
# by `leaf_dev.record_demo`, relative to the asset tree. An example names its own
# catalog preview instead.
SOCIAL_CARD = "demo/session-card.png"


class Links(HTMLParser):
    """Every href/src/srcset in a document, in source order."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if not value:
                continue
            if name in ("href", "src"):
                self.found.append(value)
            elif name == "srcset" and not value.lstrip().startswith("data:"):
                # Exported media is one data URL whose payload contains a comma. It is
                # already self-contained, so do not parse that comma as a candidate
                # boundary. Authored local candidates use the ordinary srcset form.
                self.found += [
                    c.strip().split()[0] for c in value.split(",") if c.strip()
                ]


def local_targets(html: str) -> list[str]:
    """The links a static host has to serve itself: same-origin, and naming a file."""
    parser = Links()
    parser.feed(html)
    targets = []
    for link in parser.found:
        parts = urlsplit(link)
        if parts.scheme or parts.netloc or not parts.path:
            continue  # absolute, protocol-relative, data:, or a bare #fragment
        targets.append(unquote(parts.path))
    return targets


def published_pages(
    out: Path, *, include_products: bool = True
) -> list[tuple[Path, str]]:
    """The page directories and clean public roots the website server projects."""
    product = (
        [
            (product_page(out, source.name), PRODUCT_ROUTES[source.name].rstrip("/"))
            for source in product_sources()
        ]
        if include_products
        else []
    )
    examples = [
        (page, f"/examples/{page.name}")
        for page in sorted((out / "examples").iterdir())
        if (page / "events.jsonl").is_file()
    ]
    return product + examples


def resolves(out: Path, pages: list[tuple[Path, str]], url: str) -> bool:
    """Resolve one public URL through the same longest-page-root rule as the server."""
    path = unquote(urlsplit(url).path)
    physical = out / path.lstrip("/")
    if physical.is_file():
        return True
    for page_dir, page_root in sorted(
        pages, key=lambda item: len(item[1]), reverse=True
    ):
        if path == page_root or path == f"{page_root}/":
            return (page_dir / "index.html").is_file()
        prefix = f"{page_root}/" if page_root else "/"
        if path.startswith(prefix):
            named = page_dir / path[len(prefix) :]
            return (
                (named / "index.html").is_file()
                if path.endswith("/")
                else named.exists()
            )
    return False


def check_links(out: Path) -> None:
    dead = []
    pages = published_pages(out)
    for page_dir, page_root in pages:
        for page in sorted(page_dir.rglob("*.html")):
            relative = page.relative_to(page_dir)
            html = rebase_document(
                page.read_text(encoding="utf-8"),
                DeliveryAddress(page_root, page_root),
            )
            public_page = f"{page_root}/{relative}" if page_root else f"/{relative}"
            for target in local_targets(html):
                public_target = urljoin(public_page, target)
                if not resolves(out, pages, public_target):
                    dead.append(f"{public_page} → {target}")
    # A card image is named in a content attribute rather than an href, so the sweep
    # above never sees it: an unfurled link is the one surface whose broken image
    # nobody browsing the site would notice.
    manifest = json.loads((out / SITE_MANIFEST).read_text(encoding="utf-8"))
    for route, page in sorted(manifest["pages"].items()):
        if not resolves(out, pages, page["image"]):
            dead.append(f"{route} → {page['image']} (og:image)")
    if dead:
        sys.exit(
            "the site would publish links that reach nothing:\n  " + "\n  ".join(dead)
        )


def leaf(env: dict, *args: str, input_text: str | None = None) -> None:
    """A leaf command, quiet unless it fails, and then exiting with what it said."""
    done = subprocess.run(
        [*LEAF_COMMAND, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
        check=False,
    )
    if done.returncode:
        sys.exit(f"leaf {' '.join(args)}:\n{done.stdout}{done.stderr}")


def published_page_sources() -> list[Path]:
    """Authored pages the public site publishes, including developer references."""
    worked = [
        source
        for source in sorted(EXAMPLES.glob("*.html"))
        if source.stem not in INTERNAL_EXAMPLES
    ]
    return [*worked, *DEVELOPER_PAGES]


def product_sources() -> list[Path]:
    """The product documents, one per public route."""
    return [DOCS / name for name in PRODUCT_ROUTES]


def product_page(out: Path, source_name: str) -> Path:
    """The independent page directory behind one product source's public route."""
    return out / "_leaf" / "pages" / Path(source_name).stem


def asset_site(out: Path) -> Path:
    """The sibling tree exposed through Cloudflare's static asset binding."""
    return out.with_name(f"{out.name}-assets")


def media_url(source: Path) -> str:
    """The page path an image takes once `leaf page media` has stored it."""
    return f"/{MEDIA_DIR}/{media_name(source.read_bytes(), source.suffix)}"


def social_images(assets: Path) -> dict[str, str]:
    """The public card image behind each page root.

    Both are named at the page root that publishes the file: the product shot at the
    site root, and an example's preview in the catalog, which is the page the previews
    were stored against. Every root serves the whole media set, so the two paths hold
    for a card unfurled from any page.
    """
    catalog = PRODUCT_ROUTES["examples.html"].rstrip("/")
    images = {
        f"{catalog}/{source.stem}": catalog
        + media_url(assets / "examples" / f"example-{source.stem}.jpg")
        for source in catalog_sources()
    }
    return {"": media_url(assets / SOCIAL_CARD), **images}


def document_metadata(page_dir: Path) -> tuple[str, str]:
    """The title and description a published page authored; a crawler and an
    unfurled link show exactly these two, so the build refuses a page missing either."""
    parsed = SourceDocument((page_dir / "index.html").read_text(encoding="utf-8"))
    title = parsed.title.strip()
    description = next(
        (
            (meta["content"] or "").strip()
            for meta in parsed.named_metas
            if meta["name"] == "description"
        ),
        "",
    )
    if not title or not description:
        sys.exit(f"{page_dir.name}: a published page needs a <title> and a description")
    return title, description


def write_crawler_directives(assets: Path, routes: list[str]) -> None:
    """Publish the two files a crawler reads before it reads a page.

    Nothing is disallowed: the version and revision documents a page also publishes
    are settled by their canonical link, and a crawler has to fetch them to read it.

    The content signals are stated rather than left open, because Cloudflare's managed
    robots.txt otherwise supplies `search=yes, ai-train=no` for a zone that says
    nothing, and this site wants to be read by all three.
    """
    (assets / "robots.txt").write_text(
        "User-agent: *\n"
        "Content-Signal: search=yes, ai-input=yes, ai-train=yes\n"
        "Allow: /\n"
        f"\nSitemap: {SITE_ORIGIN}/sitemap.xml\n",
        encoding="utf-8",
    )
    locations = "".join(
        f"  <url><loc>{SITE_ORIGIN}{route.rstrip('/')}/</loc></url>\n"
        for route in routes
    )
    (assets / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{locations}</urlset>\n",
        encoding="utf-8",
    )


def deduplicate_tree(root: Path, *, mutable_names: set[str] = frozenset()) -> None:
    """Hard-link identical build outputs without changing their public paths.

    `mutable_names` names files, or directories whose files, a served page rewrites;
    those keep their own inodes."""
    canonical: dict[tuple[int, bytes], Path] = {}
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        if path.name in mutable_names or path.parent.name in mutable_names:
            continue
        body = path.read_bytes()
        identity = (len(body), hashlib.sha256(body).digest())
        existing = canonical.setdefault(identity, path)
        if existing == path:
            continue
        path.unlink()
        os.link(existing, path)


def publish_examples(out: Path, env: dict) -> None:
    """Publish worked examples and developer references without product pages."""
    for source in published_page_sources():
        published = out / "examples" / source.stem
        fixture = read_fixture(source)
        prepare_page(
            published,
            fixture,
            partial(leaf, env),
            final_status="idle",
            current_note="As published",
        )
        print(f"  {source.stem}")


def publish_pages(out: Path, env: dict, assets: Path) -> None:
    """Canonical interactive product documents and worked examples."""
    with tempfile.TemporaryDirectory() as tmp:
        template = Path(tmp) / "product-page"
        packages = json.loads((EXAMPLES / "layer.json").read_text(encoding="utf-8"))
        selection = package_selection_args([*packages, SITE_PACKAGE])
        leaf(env, "page", "init", *selection, str(template))
        # Put the authored images behind the content-addressed paths the product
        # sources name before validating and rendering them.
        product_media = [
            assets / SOCIAL_CARD,
            *(
                assets / "examples" / f"example-{source.stem}.jpg"
                for source in catalog_sources()
            ),
        ]
        leaf(env, "page", "media", str(template), *map(str, product_media))
        # Each product document is checked in the template, then published as a copy.
        for source in product_sources():
            shutil.copyfile(source, template / "index.html")
            leaf(env, "page", "check", str(template))
            target = product_page(out, source.name)
            shutil.copytree(template, target)
            leaf(env, "page", "stamp", str(target), "--text", "As published")
            leaf(env, "status", str(target), "idle")
    publish_examples(out, env)


def publish_live_shells(
    out: Path, assets: Path, *, include_products: bool = True
) -> Path:
    """Materialize the public bytes of every private page directory."""
    images = social_images(assets)
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in out.rglob("*") if candidate.is_file()
    ):
        digest.update(path.relative_to(out).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    release = os.environ.get("LEAF_SITE_RELEASE", digest.hexdigest())
    assets = asset_site(out)
    shutil.rmtree(assets, ignore_errors=True)
    assets.mkdir(parents=True)
    # The Worker routes a page's namespace, and frames the HTML it serves from its own
    # assets, from here rather than from copies of its own.
    manifest = {
        "release": release,
        "frame_ancestors": FRAME_ANCESTORS_CSP,
        "routes": {
            "layer": list(BROWSER_DIRS),
            "session": list(SESSION_ROUTE_DIRS),
            "files": list(VENDORED_FILES),
        },
        "pages": {},
    }
    for page_dir, page_root in published_pages(out, include_products=include_products):
        destination = assets / page_root.lstrip("/")
        key = "root" if page_root == "" else page_root.strip("/").replace("/", "--")
        asset_root = f"/_leaf-release/{release}/{key}"
        kind = "example" if page_root.startswith("/examples/") else "product"
        states = {}
        current = latest_revision(page_dir)
        for revision in list_revisions(page_dir):
            state_path = f"/_leaf/state/{key}--r{revision}.json"
            state = initial_state(page_dir, page_root, kind, release, revision)
            state_file = assets / state_path.lstrip("/")
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            states[str(revision)] = state_path
        state_path = states[str(current)]
        state = initial_state(page_dir, page_root, kind, release)
        title, description = document_metadata(page_dir)
        entry = {
            "directory": page_dir.relative_to(out).as_posix(),
            "assets": asset_root,
            "kind": kind,
            "layer": state["layer"]["generation"],
            "state": state_path,
            "states": states,
            "title": title,
            "description": description,
            "image": images.get(page_root, images[""]),
        }
        manifest["pages"][page_root or "/"] = entry
        write_live_shell(
            page_dir,
            destination,
            page_root=page_root,
            release_id=release,
            asset_root=asset_root,
            head=site_metadata(page_root, entry),
        )
    write_crawler_directives(assets, sorted(manifest["pages"]))
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    for tree in (out, assets):
        (tree / SITE_MANIFEST).parent.mkdir(parents=True, exist_ok=True)
        (tree / SITE_MANIFEST).write_text(manifest_text, encoding="utf-8")
    deduplicate_tree(assets)
    deduplicate_tree(
        out,
        mutable_names={
            "cursor.json",
            "data",
            "data.json",
            "events.jsonl",
            "interactions.jsonl",
            "index.html",
            "service.json",
            "status.json",
        },
    )
    return assets


def build_examples(out: Path, *, assets: Path) -> None:
    """Build only the public example routes used to record catalog previews."""
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    # `environment()` keeps the builder's host session out of published version notes.
    publish_examples(out, environment())
    publish_live_shells(out, assets, include_products=False)


def build(out: Path, *, assets: Path | None = None) -> None:
    assets = assets or pinned_assets()
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    publish_pages(out, environment(), assets)
    publish_live_shells(out, assets)
    check_links(out)


def bundle_published_runtime(out: Path) -> None:
    """Collapse the public static module graph after its routes have been scoped."""
    done = subprocess.run(
        ["node", str(BUNDLE_RUNTIME), str(asset_site(out))],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        sys.exit(f"website runtime bundle failed:\n{done.stdout}{done.stderr}")
    deduplicate_tree(asset_site(out))


@click.command("site")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=OUT,
    help="Build destination (default: .tmp/site).",
)
def site(output: Path) -> None:
    """Build leaf.page and its edge assets."""
    from leaf.session_cleanup import flocked

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # One destination is one publication; independent builds use separate outputs.
    with flocked(output.with_name(f"{output.name}.lock")):
        build(output)
        bundle_published_runtime(output)
    click.echo(
        f"✓ {len(list(output.rglob('*.html')))} pages → {output} and {asset_site(output)}"
    )
