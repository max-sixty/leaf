#!/usr/bin/env python3
"""Assemble the published site (https://leaf.page/) into .tmp/site.

Every product document under `docs/` is a Leaf source. The build publishes all five as
complete page directories, alongside the worked examples. The Worker serves the
build-generated initial projection at the edge, then gives an interacting browser a
private copy through Leaf's canonical Python server. The catalog previews come from the
external revision pinned in `example-previews.json`.

The worked examples and developer package galleries become complete Leaf page directories
under examples/<name>/. The same preparation path that serves a local fixture vendors
each page's selected layer, stamps its authored versions, applies its companion event
log and data, and closes the finished page without claiming it for an agent. A second,
derived tree contains the immutable live shell Cloudflare serves before the canonical
server answers its API requests.

A dead link is the failure a static host cannot report, so the build resolves every
local href and src it wrote and refuses a site holding one that names no file.

Usage: uv run scripts/site.py [--serve]
       (writes .tmp/site; --serve keeps a local preview open)
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from functools import partial
from html.parser import HTMLParser
from importlib import import_module
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from example_assets import example_previews
from example_data import catalog_sources
from leaf.files import latest_revision, list_revisions
from leaf.http import scope_document_routes
from leaf.live_shell import write_live_shell
from leaf.media import media_name
from leaf.schema import MEDIA_DIR
from leaf.structure import SourceDocument
from page_fixtures import prepare_page, read_fixture

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
worker_server = import_module("worker.server")
SITE_MANIFEST = worker_server.SITE_MANIFEST
SITE_ORIGIN = worker_server.SITE_ORIGIN
initial_state = worker_server.initial_state
site_head = worker_server.site_head

LEAF = ROOT / "bin" / "leaf"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
INTERNAL_EXAMPLES = {"corpus"}
DEVELOPER_PAGES = tuple(sorted((EXAMPLES / "developer").glob("*.html")))
OUT = (
    ROOT / ".tmp" / "site"
)  # gitignored; the container consumes the complete private page directories
WRANGLER = ROOT / "worker" / "node_modules" / ".bin" / "wrangler"
BUNDLE_RUNTIME = ROOT / "worker" / "bundle-runtime.mjs"

PRODUCT_ROUTES = {
    "index.html": "/",
    "examples.html": "/examples/",
    "how-it-works.html": "/how-it-works/",
    "packages.html": "/packages/",
    "registry.html": "/registry/",
}
SITE_PACKAGE = "./docs/package"
# The card a link to a product page unfurls into. An example names its own catalog
# preview instead, so a shared example shows the page rather than the product shot.
#
# Its own file rather than the landing page's still, because the two are shown at
# different shapes: an unfurler draws a card at 1.91:1, and the still is 4:3, so
# serving the still here handed every reader a centre crop of it with the banner cut
# off the top — the version control, the approval, the thread count, everything that
# says a page is live. `record-demo.py` shoots this off the same scene at the card's
# own shape, so it stays as true as the stills beside it.
DEFAULT_SOCIAL_IMAGE = DOCS / "session-card.png"


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


def published_pages(out: Path) -> list[tuple[Path, str]]:
    """The page directories and clean public roots the website server projects."""
    product = [
        (product_page(out, source.name), PRODUCT_ROUTES[source.name].rstrip("/"))
        for source in product_sources()
    ]
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
            html = scope_document_routes(page.read_bytes(), page_root)
            public_page = f"{page_root}/{relative}" if page_root else f"/{relative}"
            for target in local_targets(html.decode()):
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
    """A leaf command, quiet unless it fails — and then failing with what it said. The
    output is the whole of a refused check's news, and a build that swallowed it stopped
    on a traceback naming this file about a fault in an example."""
    done = subprocess.run(
        [str(LEAF), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
        check=False,
    )
    if done.returncode:
        sys.exit(f"leaf {' '.join(args)}:\n{done.stdout}{done.stderr}")


def worked_example_sources() -> list[Path]:
    """Authored worked examples, never derived or developer test surfaces."""
    sources = [
        source
        for source in sorted(EXAMPLES.glob("*.html"))
        if source.stem not in INTERNAL_EXAMPLES
    ]
    if not sources:
        sys.exit("examples/ holds no authored pages to publish")
    return sources


def published_page_sources() -> list[Path]:
    """Authored pages the public site publishes, including developer references."""
    if not DEVELOPER_PAGES:
        sys.exit("examples/developer holds no authored pages")
    return [*worked_example_sources(), *DEVELOPER_PAGES]


def product_sources() -> list[Path]:
    """The complete product-page set, held to the public route map."""
    sources = sorted(DOCS.glob("*.html"))
    found = {source.name for source in sources}
    expected = set(PRODUCT_ROUTES)
    if found != expected:
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        sys.exit(
            f"product pages disagree with their routes: missing={missing}, extra={extra}"
        )
    return sources


def product_page(out: Path, source_name: str) -> Path:
    """The independent page directory behind one product source's public route."""
    return out / "_leaf" / "pages" / Path(source_name).stem


def asset_site(out: Path) -> Path:
    """The sibling tree exposed through Cloudflare's static asset binding."""
    return out.with_name(f"{out.name}-assets")


def media_url(source: Path) -> str:
    """The page path an image takes once `leaf page media` has stored it."""
    return f"/{MEDIA_DIR}/{media_name(source.read_bytes(), source.suffix.lower())}"


def social_images(catalog_previews: Path | None = None) -> dict[str, str]:
    """The public card image behind each page root.

    Both are named at the page root that publishes the file: the product shot at the
    site root, and an example's preview in the catalog, which is the page the previews
    were stored against. Every root serves the whole media set, so the two paths hold
    for a card unfurled from any page.
    """
    previews = catalog_previews or example_previews()
    catalog = PRODUCT_ROUTES["examples.html"].rstrip("/")
    images = {
        f"{catalog}/{source.stem}": catalog
        + media_url(previews / f"example-{source.stem}.jpg")
        for source in catalog_sources()
    }
    return {"": media_url(DEFAULT_SOCIAL_IMAGE), **images}


def document_metadata(page_dir: Path) -> tuple[str, str]:
    """What a published page says it is: the title and description it authored.

    The build refuses a page missing either, because a crawler and an unfurled link
    show exactly these two and have nothing else to fall back to.
    """
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
        missing = " and ".join(
            part
            for part, present in (("<title>", title), ("a description", description))
            if not present
        )
        sys.exit(f"{page_dir.name}: a published page needs {missing}")
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
    """Hard-link identical build outputs without changing their public paths."""
    canonical: dict[tuple[int, bytes], Path] = {}
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        if path.name in mutable_names:
            continue
        body = path.read_bytes()
        identity = (len(body), hashlib.sha256(body).digest())
        existing = canonical.setdefault(identity, path)
        if existing == path:
            continue
        path.unlink()
        os.link(existing, path)


def checked_product_sources(page: Path, env: dict) -> list[tuple[Path, bytes]]:
    """Validate every product document before publishing any of them."""
    checked = []
    for source in product_sources():
        markup = source.read_bytes()
        (page / "index.html").write_bytes(markup)
        leaf(env, "version", "check", str(page))
        checked.append((source, markup))
    return checked


def publish_product_pages(
    page: Path, out: Path, products: list[tuple[Path, bytes]], env: dict
) -> None:
    """Publish every validated product document as a complete Leaf page."""
    for source, markup in products:
        target = product_page(out, source.name)
        shutil.copytree(page, target)
        (target / "index.html").write_bytes(markup)
        leaf(env, "version", "stamp", str(target), "--text", "As published")
        leaf(env, "status", str(target), "idle")


def publish_pages(out: Path, env: dict, catalog_previews: Path | None = None) -> None:
    """Canonical interactive product documents and worked examples."""
    with tempfile.TemporaryDirectory() as tmp:
        product_page = Path(tmp) / "product-page"
        packages = json.loads((EXAMPLES / "layer.json").read_text(encoding="utf-8"))
        selection_args = [arg for name in packages for arg in ("--package", name)]
        selection_args.extend(("--package", SITE_PACKAGE))
        leaf(env, "page", "init", *selection_args, str(product_page))
        # Put the authored images behind the content-addressed paths the product
        # sources name before validating and rendering them.
        product_media = sorted(
            path for pattern in ("*.gif", "*.png") for path in DOCS.glob(pattern)
        )
        preview_source = catalog_previews or example_previews()
        product_media.extend(
            preview_source / f"example-{source.stem}.jpg"
            for source in catalog_sources()
        )
        leaf(
            env,
            "page",
            "media",
            str(product_page),
            *(str(path) for path in product_media),
        )
        products = checked_product_sources(product_page, env)
        publish_product_pages(product_page, out, products, env)
        shutil.copy2(DOCS / "sitenote.js", out / "sitenote.js")

        for source in published_page_sources():
            published = out / "examples" / source.stem
            prepare_page(
                published,
                read_fixture(source),
                partial(leaf, env),
                final_status="idle",
                current_note="As published",
            )
            print(f"  {source.stem}")


def publish_live_shells(out: Path, catalog_previews: Path | None = None) -> Path:
    """Materialize the public bytes of every private page directory."""
    images = social_images(catalog_previews)
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in out.rglob("*") if candidate.is_file()
    ):
        digest.update(path.relative_to(out).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    release = os.environ.get("LEAF_SITE_RELEASE", digest.hexdigest())
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", release):
        raise ValueError("LEAF_SITE_RELEASE must be a full git or SHA-256 hex digest")
    assets = asset_site(out)
    shutil.rmtree(assets, ignore_errors=True)
    assets.mkdir(parents=True)
    manifest = {"release": release, "pages": {}}
    for page_dir, page_root in published_pages(out):
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
        if current is None:
            raise ValueError(f"{page_dir} has no active revision")
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
            before_runtime=site_head(page_root, entry, asset_root=asset_root),
        )
        if kind == "example":
            shutil.copy2(out / "sitenote.js", destination / "sitenote.js")
    shutil.copy2(out / "sitenote.js", assets / "sitenote.js")
    write_crawler_directives(assets, sorted(manifest["pages"]))
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    private_manifest = out / SITE_MANIFEST
    private_manifest.parent.mkdir(parents=True, exist_ok=True)
    private_manifest.write_text(manifest_text, encoding="utf-8")
    public_manifest = assets / SITE_MANIFEST
    public_manifest.parent.mkdir(parents=True, exist_ok=True)
    public_manifest.write_text(manifest_text, encoding="utf-8")
    deduplicate_tree(assets)
    deduplicate_tree(
        out,
        mutable_names={
            "cursor.json",
            "data.json",
            "events.jsonl",
            "index.html",
            "service.json",
            "status.json",
        },
    )
    return assets


def build(
    out: Path,
    *,
    verify_links: bool = True,
    catalog_previews: Path | None = None,
) -> None:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    # The layer a visitor gets is the shipped one, plus this project's: a page dir
    # vendors the user's ~/.config/leaf overlay too, and that one belongs to
    # whoever is running the build. An empty config home is what withholds it —
    # HOME stays, because uv keeps its cache there and a moved HOME re-downloads
    # Playwright on every build. Dropping the session leaves these throwaway page
    # directories nobody's, and so out of the watch guard.
    #
    # The state home stays whole, and wants no emptying beside the config one:
    # what writes there is `server run`'s and `leaf wait`'s — the machine key,
    # the session's claim — and a build runs neither.
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAF_")}
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env.pop("CODEX_THREAD_ID", None)
    with tempfile.TemporaryDirectory() as config_home:
        env["XDG_CONFIG_HOME"] = config_home
        publish_pages(out, env, catalog_previews)
    publish_live_shells(out, catalog_previews)

    if verify_links:
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


def main() -> None:
    if sys.argv[1:] not in ([], ["--serve"]):
        sys.exit("usage: uv run scripts/site.py [--serve]")
    build(OUT)
    bundle_published_runtime(OUT)
    print(f"✓ {len(list(OUT.rglob('*.html')))} pages → {OUT} and {asset_site(OUT)}")
    if sys.argv[1:] == ["--serve"]:
        if not WRANGLER.is_file():
            sys.exit("website dependencies are missing; run `npm ci --prefix worker`")
        print("Preview: http://127.0.0.1:8787/examples/")
        result = subprocess.run(
            [str(WRANGLER), "dev"], cwd=ROOT / "worker", check=False
        )
        if result.returncode:
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
