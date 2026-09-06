#!/usr/bin/env python3
"""Assemble the published site (https://leaf.page/) into .tmp/site.

Every product document under `docs/` is a Leaf source. The build checks all five in one
temporary page directory, then publishes their browser-drawn standalone exports through
one shared browser. Each export gets an isolated browser context, inlines the composed
theme and media, retains the rendered widgets, and removes runtime scripts and controls.

The worked examples and developer feature gallery become complete Leaf page directories
under examples/<name>/. The same preparation path that serves a local fixture vendors
each page's selected layer, stamps its authored versions, applies its companion event
log and data, and closes the finished page without claiming it for an agent. The Worker
gives each browser a private copy of those directories and the canonical server projects
their virtual routes.

A dead link is the failure a static host cannot report, so the build resolves every
local href and src it wrote and refuses a site holding one that names no file.

Usage: uv run scripts/site.py [--serve]
       (writes .tmp/site; --serve keeps a local preview open)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from leaf.exporting import export_page
from leaf.http import scope_document_routes
from leaf.render_gate.browser import browser_hint, launch_browser
from leaf.render_gate.preview import preview_server
from preview import prepare

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "bin" / "leaf"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
INTERNAL_EXAMPLES = {"corpus"}
FEATURE_GALLERY = EXAMPLES / "developer" / "feature-gallery.html"
OUT = (
    ROOT / ".tmp" / "site"
)  # gitignored; both the Worker asset binding and its container image consume it
WRANGLER = ROOT / "worker" / "node_modules" / ".bin" / "wrangler"

PRODUCT_ROUTES = {
    "index.html": "/",
    "examples.html": "/examples/",
    "how-it-works.html": "/how-it-works/",
    "packages.html": "/packages/",
    "registry.html": "/registry/",
}
SITE_PACKAGE = "./docs/package"


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


def resolves(out: Path, page: Path, target: str) -> bool:
    """A leading slash is the site's root; anything else is where it was written.

    A target naming a directory is what the host answers with that directory's index, so
    that is what has to be there — a link to examples/triage-board/ with no index in it
    resolves to a listing on one host and a 404 on this one."""
    base = out if target.startswith("/") else page.parent
    named = base / target.lstrip("/")
    return (named / "index.html").is_file() if target.endswith("/") else named.exists()


def check_links(out: Path) -> None:
    dead = []
    for page in sorted(out.rglob("*.html")):
        relative = page.relative_to(out)
        html = page.read_bytes()
        if len(relative.parts) >= 3 and relative.parts[0] == "examples":
            html = scope_document_routes(html, f"/examples/{relative.parts[1]}")
        for target in local_targets(html.decode()):
            if not resolves(out, page, target):
                dead.append(f"{relative} → {target}")
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
    """Authored pages the public site publishes, including its developer reference."""
    if not FEATURE_GALLERY.is_file():
        sys.exit("the developer feature gallery is missing")
    return [*worked_example_sources(), FEATURE_GALLERY]


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


def product_target(out: Path, route: str) -> Path:
    """The index file a canonical trailing-slash route serves."""
    return out / "index.html" if route == "/" else out / route.strip("/") / "index.html"


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
    page: Path, out: Path, products: list[tuple[Path, bytes]], browser
) -> None:
    """Publish validated product documents through one shared browser."""
    for source, markup in products:
        (page / "index.html").write_bytes(markup)
        with preview_server(page, markup, 1) as url:
            exported = export_page(browser, url, page, source.name)
        target = product_target(out, PRODUCT_ROUTES[source.name])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(exported, encoding="utf-8")


def publish_pages(out: Path, env: dict, browser=None) -> None:
    """Standalone product documents and canonical interactive pages."""
    with tempfile.TemporaryDirectory() as tmp:
        product_page = Path(tmp) / "product-page"
        packages = json.loads((EXAMPLES / "layer.json").read_text(encoding="utf-8"))
        selection_args = [arg for name in packages for arg in ("--package", name)]
        selection_args.extend(("--package", SITE_PACKAGE))
        leaf(env, "page", "init", *selection_args, str(product_page))
        # Put the authored images behind the content-addressed paths the product
        # sources name before validating and rendering them.
        product_media = sorted(
            path
            for pattern in ("*.gif", "*.jpg", "*.png")
            for path in DOCS.glob(pattern)
        )
        leaf(
            env,
            "page",
            "media",
            str(product_page),
            *(str(path) for path in product_media),
        )
        products = checked_product_sources(product_page, env)
        if browser is not None:
            publish_product_pages(product_page, out, products, browser)
        else:
            try:
                from playwright.sync_api import Error as PlaywrightError
                from playwright.sync_api import sync_playwright
            except ImportError:
                sys.exit("the site build needs Playwright to render its product pages")
            with sync_playwright() as playwright:
                try:
                    launched, _ = launch_browser(playwright)
                except PlaywrightError as error:
                    sys.exit(
                        "the site build needs a browser, and none launched "
                        f"({str(error).strip().splitlines()[0]}). {browser_hint()}"
                    )
                try:
                    publish_product_pages(product_page, out, products, launched)
                finally:
                    launched.close()
        # The social card is the reference that keeps this: every page names its
        # og:image at an absolute https://leaf.page/media/… URL, which no export
        # inlines and no link check can see. The rest is already in the exports.
        shutil.copytree(product_page / "media", out / "media")
        shutil.copy2(DOCS / "sitenote.js", out / "sitenote.js")

        for source in published_page_sources():
            published = out / "examples" / source.stem
            prepare(
                source,
                published,
                LEAF,
                ROOT,
                env=env,
                final_status="idle",
                current_note="As published",
            )
            print(f"  {source.stem}")


def build(out: Path, *, verify_links: bool = True, browser=None) -> None:
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
        publish_pages(out, env, browser)

    if verify_links:
        check_links(out)


def main() -> None:
    if sys.argv[1:] not in ([], ["--serve"]):
        sys.exit("usage: uv run scripts/site.py [--serve]")
    build(OUT)
    print(f"✓ {len(list(OUT.rglob('*.html')))} pages → {OUT}")
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
