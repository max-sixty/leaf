#!/usr/bin/env python3
"""Assemble the published site (https://leaf.page/) into .tmp/site.

The site is the pages the repo already holds. `docs/` is written to be opened from
a checkout — the worn assets (`WORN`) arrive by relative paths into the plugin
payload, and payload and example links point into the checkout — so publishing is
those substitutions plus the files the paths then name. An example keeps its authored
document and gains only the site-only startup marker below; that narrow transformation
lets the files in the tree remain the specimens of the theme.

The examples are the files in the tree too, and they are live. A leaf page is a
directory — the vendored layer at a root, the versions under it — and a static host
serves every part of that; the one thing it hasn't got is the process behind /api/state,
/api/event, and /api/news. So the build lays one vendored layer at the site's root,
where a page's absolute /theme.css and /leaf.js resolve, and puts each example at its
own examples/<name>/versions/, which is where the runtime reads a version number from.
An example that ships a prior version publishes every one of them, so the chooser on
the published page travels and marks the same way the served page's does. The
published root wears `data-lf-eager`, so the shipped theme can paint the authored
page before this site's JavaScript arrives without changing that rule for a served
Leaf page. What answers the three paths is `docs/session.js`, loaded in front of
the runtime by `docs/leaf.js`: the log lives in the reader's own tab. Every control on
the page is then the shipped one, working — the banner, the thread panel, a board that
takes a drag and holds it. The half no host can supply is the agent at the other end:
the page reports itself unattended and the banner says so in the runtime's own words,
and `docs/sitenote.js` says the whole of it in the site's own label above the document.

A dead link is the failure a static host cannot report, so the build resolves every
local href and src it wrote and refuses a site holding one that names no file.

Usage: site.py [--serve]  (writes .tmp/site; --serve keeps a local preview open)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from example_data import data_operations, example_versions

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "bin" / "leaf"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
INTERNAL_EXAMPLES = {"corpus"}
OUT = (
    ROOT / ".tmp" / "site"
)  # gitignored; the workflow uploads it as the Pages artifact

REPO = "https://github.com/max-sixty/leaf"

# The one name the site changes on the way past. /leaf.js is the door a page and every
# widget module import comes through, and on this site that door is `docs/leaf.js` — the
# runtime with a session in front of it — so the vendored runtime is published beside it
# under the name that file imports. Everything else in the page directory keeps its name,
# and nothing here lists what that is: the layer is whatever `page init` wrote, so a file
# it gains is a file the site serves rather than one it silently leaves behind.
RUNTIME = "runtime.js"

# The payload files a docs page is *wearing* rather than pointing at: the stylesheet it
# is styled by and the icon its tab shows. Every other path into the payload is source to
# read and becomes a GitHub link (PAYLOAD_SOURCE); these have to resolve on the host, so
# link is rewritten to name the site's own copy — which is the vendored layer's, so the
# site is styled by the file its examples are styled by rather than by a second copy of
# the same rules. Rewritten first and on their own, and the rule has to say *the link
# element's* href — `packages.html` also links the stylesheet as source to read, and a
# match on the path alone would send a reader after the token block to the copy the site
# serves instead of to the source.
#
# A pattern rather than a literal, because the literal is the same rule with a
# formatter's opinion baked into it. It read as the whole <link> tag until prettier
# started writing the void element `<link … />` and splitting this one over four lines;
# the literal quietly stopped matching, the generic ../skills/ rule below took the href
# instead, and every page shipped with its stylesheet pointing at a GitHub blob view —
# a link that resolves, so the dead-link check has nothing to say, over a page with no
# theme on it.
PAYLOAD = "../skills/leaf"
WORN = {
    f"{PAYLOAD}/assets/theme.css": "theme.css",
    f"{PAYLOAD}/assets/icon.svg": "icon.svg",
}
WORN_LINKS = {
    name: re.compile(rf'(<link\b[^>]*?)"{re.escape(source)}"')
    for source, name in WORN.items()
}
# The one link a page loses here. A checkout has no merged stylesheet to link, so a docs
# page names both halves of the theme; the site serves the merged file a page directory
# vendors, which already holds this one — linked again it would restate the default half
# over the top of itself.
DEFAULT_THEME = re.compile(
    rf'\s*<link\b[^>]*?"{re.escape(f"{PAYLOAD}/packages/default/theme.css")}"[^>]*>'
)

# Everything else a page reaches into the payload for is source to read, and becomes the
# link that reads it. Both sides are literal, so a page naming something else keeps what
# it named and the link check below is what notices.
PAYLOAD_SOURCE = ("../skills/", f"{REPO}/blob/main/skills/")
# An example is a page directory here, so its link is the directory rather than a file:
# examples/triage-board/ , where the index below sends a reader on to the version file.
# A live server can keep the root address because it injects the exact projected-version
# marker into that response; this static host has no changing root response to mark.
EXAMPLE_LINK = re.compile(r"\.\./examples/([a-z0-9-]+)\.html")

# A static showcase has no server response that could reconcile a prior log before paint,
# so its immutable authored version is safe to show while this site's in-tab session
# starts. CSS needs the fact in the document before an external module arrives. A served
# Leaf page retains the ordinary presentation gate because its source has no marker.
EAGER_ROOT = re.compile(r"<html(?=[\s>])", flags=re.IGNORECASE)


def eager_example(html: str) -> str:
    if len(EAGER_ROOT.findall(html)) != 1:
        raise ValueError("a published example must have exactly one html root")
    return EAGER_ROOT.sub("<html data-lf-eager", html, count=1)


# A static showcase has no server response that can stamp a live root with the version
# it projected, so the directory's index forwards to the newest immutable file — every
# earlier one is published beside it, which is what the chooser travels to. Both routes
# are present because a 0-second meta refresh leaves a history entry on some engines and
# the back button then bounces forward off it.
REDIRECT = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>leaf</title>
    <link rel="canonical" href="versions/{name}" />
    <noscript><meta http-equiv="refresh" content="0; url=versions/{name}" /></noscript>
    <script>
      location.replace("versions/{name}");
    </script>
  </head>
  <body>
    <a href="versions/{name}">Open the page</a>
  </body>
</html>
"""


def newest_version(source: Path) -> str:
    """The version file a reader of this example lands on."""
    return f"v{len(example_versions(source))}.html"


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


def publish_pages(out: Path, env: dict) -> None:
    """The corpus's vendored layer and every authored example at the site root."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page"
        packages = json.loads((EXAMPLES / "layer.json").read_text(encoding="utf-8"))
        selection_args = [arg for name in packages for arg in ("--package", name)]
        leaf(env, "page", "init", *selection_args, str(page))
        # The page's content, named by the hash of its bytes and served from the root the
        # markup names it at (/media/…). It goes in the page directory rather than
        # straight to the site, because `version check` refuses a reference the directory
        # can't answer — and from there it is published with everything else below.
        shutil.copytree(EXAMPLES / "media", page / "media", dirs_exist_ok=True)
        for item in sorted(page.iterdir()):
            if item.name == "versions":
                continue  # each example is its own, below
            target = out / (RUNTIME if item.name == "leaf.js" else item.name)
            (shutil.copytree if item.is_dir() else shutil.copy2)(item, target)

        for source in example_sources():
            # The temporary page is reused only for its vendored layer. Reset its
            # authored history so every independently published example starts at
            # r1/v1, then let the real stamp boundary create both immutable files.
            for directory in (page / "revisions", page / "versions"):
                directory.mkdir(exist_ok=True)
                for old in directory.iterdir():
                    old.unlink()
            log = page / "events.jsonl"
            log.write_text("", encoding="utf-8")
            # The data door validates a source against the page's markup, and the
            # current version is the one that has to bind it, so the newest version
            # goes in before the stamping loop below walks back to the oldest.
            (page / "index.html").write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
            # External data is complete replaceable source state, not a log. The
            # temporary page is reused for the corpus, so remove the prior example's
            # sources before setting this one's through the same validating door a
            # host uses.
            data_file = page / "data.json"
            data_file.unlink(missing_ok=True)
            for operation in data_operations(source):
                if operation["kind"] == "set":
                    args = ["data", "set", str(page), operation["source"]]
                    if operation["capture_label"] is not None:
                        args.extend(("--capture-label", operation["capture_label"]))
                    leaf(env, *args, input_text=json.dumps(operation["value"]))
                    continue
                args = [
                    "data",
                    "capture",
                    str(page),
                    operation["source"],
                    "--file",
                    str(operation["input_file"]),
                    "--format",
                    operation["format"],
                ]
                if operation["label"] is not None:
                    args.extend(("--label", operation["label"]))
                if operation["lines"] is not None:
                    args.extend(("--lines", operation["lines"]))
                leaf(env, *args)
            # The example's companion log, where it ships one (examples/CLAUDE.md).
            # Written rather than appended, because one page directory serves every
            # example here and an appended seed would hand the next one the last one's
            # thread. Laid after the first stamp and before any later one, so a revised
            # example's exchange reads in the order it happened, and before the check,
            # so what the gate reads is what the reader gets — an id resolving a
            # comment is a claim about this log.
            seed = source.with_suffix(".jsonl")
            seed_text = seed.read_text(encoding="utf-8") if seed.exists() else ""
            # Each authored version through the real stamp boundary, oldest first, so a
            # revised example is published with the chooser's whole list rather than the
            # one document a reader would otherwise have no way off.
            for order, authored in enumerate(example_versions(source)):
                (page / "index.html").write_text(
                    authored.read_text(encoding="utf-8"), encoding="utf-8"
                )
                leaf(
                    env,
                    "version",
                    "stamp",
                    str(page),
                    "--text",
                    f"{authored.name}, as published",
                )
                if order == 0 and seed_text:
                    with log.open("a", encoding="utf-8") as event_log:
                        event_log.write(seed_text)
            published = out / "examples" / source.stem
            (published / "versions").mkdir(parents=True)
            for version in sorted((page / "versions").iterdir()):
                (published / "versions" / version.name).write_text(
                    eager_example(version.read_text(encoding="utf-8")), encoding="utf-8"
                )
            (published / "index.html").write_text(
                REDIRECT.format(name=newest_version(source)), encoding="utf-8"
            )
            # The thread the page opens on. A served page hands its log to the browser
            # through /api/state, which is `docs/session.js`'s answer here, so the log
            # is a file beside the versions exactly as it is in a page directory and
            # that file is what the session puts in the runtime's first answer.
            (published / "events.jsonl").write_text(seed_text, encoding="utf-8")
            (published / "data.json").write_text(
                data_file.read_text(encoding="utf-8")
                if data_file.exists()
                else json.dumps({"revision": 0, "sources": {}}) + "\n",
                encoding="utf-8",
            )
            print(f"  {source.stem}")


def build(out: Path, *, verify_links: bool = True) -> None:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    for source in sorted(DOCS.iterdir()):
        target = out / source.name
        if source.suffix == ".html":
            text = source.read_text(encoding="utf-8")
            for name, pattern in WORN_LINKS.items():
                text = pattern.sub(rf'\1"{name}"', text)
            text = DEFAULT_THEME.sub("", text)
            text = EXAMPLE_LINK.sub(r"examples/\1/", text)
            text = text.replace(*PAYLOAD_SOURCE)
            target.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(source, target)

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
    with tempfile.TemporaryDirectory() as config_home:
        env["XDG_CONFIG_HOME"] = config_home
        publish_pages(out, env)

    if verify_links:
        check_links(out)


def main() -> None:
    if sys.argv[1:] not in ([], ["--serve"]):
        sys.exit("usage: site.py [--serve]")
    build(OUT)
    print(f"✓ {len(list(OUT.rglob('*.html')))} pages → {OUT}")
    if sys.argv[1:] == ["--serve"]:
        handler = partial(QuietPreview, directory=str(OUT))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        print(f"Preview: http://127.0.0.1:{server.server_address[1]}/examples.html")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
