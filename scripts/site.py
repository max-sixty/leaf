#!/usr/bin/env python3
"""Assemble the published site (https://leaf.page/) into .tmp/site.

Every product document under `docs/` is a Leaf source: it carries the exact scaffold
the version checker accepts, uses root-absolute public routes, and is published without
rewriting. The five sources become live-root directory routes, so the same runtime
addressing used by a served Leaf applies without a site-only exception.

The examples are complete Leaf page directories under examples/<name>/. The same
preparation path that serves a local example vendors each page's selected layer,
stamps its authored versions, applies its companion event log and data, and closes the
finished page without claiming it for an agent. A host can therefore route each clean
example URL through Leaf's ordinary page server instead of maintaining a second
browser-side session implementation. Product routes remain exact authored drafts and
continue to use the site's static session.

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
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from preview import prepare

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "bin" / "leaf"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
INTERNAL_EXAMPLES = {"corpus"}
OUT = (
    ROOT / ".tmp" / "site"
)  # gitignored; the workflow uploads it as the Pages artifact

# The one layer name the site changes on the way past. /leaf.js is the door a page and every
# widget module import comes through, and on this site that door is `docs/leaf.js` — the
# runtime with a session in front of it — so the vendored runtime is published beside it
# under the name that file imports. Everything else in the page directory keeps its name,
# and nothing here lists what that is: the layer is whatever `page init` wrote, so a file
# it gains is a file the site serves rather than one it silently leaves behind.
RUNTIME = "runtime.js"

PRODUCT_ROUTES = {
    "index.html": "/",
    "examples.html": "/examples/",
    "how-it-works.html": "/how-it-works/",
    "packages.html": "/packages/",
    "registry.html": "/registry/",
}
SITE_SUPPORT = ("leaf.js", "session.js", "sitenote.js")
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
            elif name == "srcset":
                self.found += [
                    c.strip().split()[0] for c in value.split(",") if c.strip()
                ]


class QuietPreview(SimpleHTTPRequestHandler):
    """Serve the local catalog without logging every module a full page imports."""

    def log_message(self, *args):
        pass


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
    dead = [
        f"{page.relative_to(out)} → {target}"
        for page in sorted(out.rglob("*.html"))
        for target in local_targets(page.read_text(encoding="utf-8"))
        if not resolves(out, page, target)
    ]
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


def example_sources() -> list[Path]:
    """Authored examples the public site publishes, never derived test surfaces."""
    sources = [
        source
        for source in sorted(EXAMPLES.glob("*.html"))
        if source.stem not in INTERNAL_EXAMPLES
    ]
    if not sources:
        sys.exit("examples/ holds no authored pages to publish")
    return sources


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


def publish_product_pages(page: Path, out: Path, env: dict) -> None:
    """Check each product document as a Leaf, then publish its exact source bytes."""
    empty_data = json.dumps({"revision": 0, "sources": {}}) + "\n"
    for source in product_sources():
        markup = source.read_text(encoding="utf-8")
        (page / "index.html").write_text(markup, encoding="utf-8")
        leaf(env, "version", "check", str(page))
        target = product_target(out, PRODUCT_ROUTES[source.name])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markup, encoding="utf-8")
        (target.parent / "data.json").write_text(empty_data, encoding="utf-8")
        (target.parent / "events.jsonl").write_text("", encoding="utf-8")


def publish_pages(out: Path, env: dict) -> None:
    """The site's vendored layer, product documents, and authored examples."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page"
        packages = json.loads((EXAMPLES / "layer.json").read_text(encoding="utf-8"))
        selection_args = [arg for name in packages for arg in ("--package", name)]
        selection_args.extend(("--package", SITE_PACKAGE))
        leaf(env, "page", "init", *selection_args, str(page))
        # The page's content, named by the hash of its bytes and served from the root the
        # markup names it at (/media/…). It goes in the page directory rather than
        # straight to the site, because `version check` refuses a reference the directory
        # can't answer — and from there it is published with everything else below.
        shutil.copytree(EXAMPLES / "media", page / "media", dirs_exist_ok=True)
        product_media = sorted(
            path
            for pattern in ("*.gif", "*.jpg", "*.png")
            for path in DOCS.glob(pattern)
        )
        leaf(env, "page", "media", str(page), *(str(path) for path in product_media))
        for item in sorted(page.iterdir()):
            target = out / (RUNTIME if item.name == "leaf.js" else item.name)
            (shutil.copytree if item.is_dir() else shutil.copy2)(item, target)

        for name in SITE_SUPPORT:
            shutil.copy2(DOCS / name, out / name)
        publish_product_pages(page, out, env)

        for source in example_sources():
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


def build(out: Path, *, verify_links: bool = True) -> None:
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
        publish_pages(out, env)

    if verify_links:
        check_links(out)


def main() -> None:
    if sys.argv[1:] not in ([], ["--serve"]):
        sys.exit("usage: uv run scripts/site.py [--serve]")
    build(OUT)
    print(f"✓ {len(list(OUT.rglob('*.html')))} pages → {OUT}")
    if sys.argv[1:] == ["--serve"]:
        handler = partial(QuietPreview, directory=str(OUT))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        print(f"Preview: http://127.0.0.1:{server.server_address[1]}/examples/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
