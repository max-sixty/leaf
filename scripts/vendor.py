#!/usr/bin/env python3
"""Rebuild the third-party bundles Leaf ships.

Nothing builds them at install time, so they are tracked. The files under
`skills/leaf/assets/vendor/` and each package's own `vendor/` are page payload:
`page init` copies them into a page directory and a user's browser runs them.
The resource under `skills/leaf/mcp-app/` is read straight from the install by
an MCP host, so no page carries it.

They arrive two ways, which is the shape of this file. Where upstream already
publishes a file a browser can load, vendoring is three values — the package,
the file inside it, and where it lands — so those are rows in COPIES. Where
nothing published is loadable as it stands, or what Leaf ships is cut down to
what its registry declares, vendoring is a program, so those are functions.

Every version they carry is the one `package-lock.json` resolved: `package.json`
names each package a bundle's entry imports, the lock settles the rest of the
closure, and every build reads the root `node_modules` that `npm ci` installs from
it. So a run after `npm ci` reproduces the tracked bytes, and a moved lock is the
only thing that moves them.

With no arguments it rebuilds everything; name bundles to redo only those.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills/leaf/assets"
PACKAGES = ROOT / "skills/leaf/packages"
MCP_APP = ROOT / "skills/leaf/mcp-app"
PIERRE_SOURCE = ROOT / "scripts/vendor-src/pierre"
NODE_MODULES = ROOT / "node_modules"


def package_vendor(package: str) -> Path:
    """Where a bundle lands, which is the package whose widget imports it.

    A vendored library is payload of the package that draws with it, not of the
    layer: Agentic Mermaid and Pierre are about 4.6MB between them and reach a
    page only when it selects `diagram` or `diff`, so a page that draws neither
    carries neither.
    """
    return PACKAGES / package / "vendor"


def version(package: str) -> str:
    """The installed version of a package, which is the one the lock resolved."""
    manifest = NODE_MODULES / package / "package.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]


class Copy(NamedTuple):
    package: str
    inside: str  # the file to take out of the published package
    out: Path


COPIES = {
    # marked is zero-dependency and its package export is already one
    # browser-native ESM file. The runtime renders every message's text with it;
    # what it may not do — pass raw HTML through, since a message injects widgets
    # only through the event's `markup` field — is configured in leaf.js.
    "marked": Copy("marked", "lib/marked.esm.js", ASSETS / "vendor/marked.esm.js"),
    # SortableJS drags lf-board's cards. The package ships its ESM entry three
    # times over, carrying the same plugin code each time and differing only in
    # which plugins it mounts, so the choice costs no bytes. This is the `module`
    # entry, which mounts the autoscroll that lf-board's `scroll` option drives.
    # `sortable.core.esm.js` mounts nothing and would drop that autoscroll;
    # `sortable.complete.esm.js` mounts swap and multi-drag on top, and lf-board
    # sets neither.
    "sortable": Copy(
        "sortablejs",
        "modular/sortable.esm.js",
        package_vendor("default") / "sortable.esm.js",
    ),
}


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def esbuild(*args: str, cwd: Path) -> None:
    run(str(NODE_MODULES / ".bin/esbuild"), *args, cwd=cwd)


def languages() -> list[str]:
    """The language names a bundle is cut to.

    They are read out of registry.json rather than stated here, because that is
    the list `version check` refuses an unknown language against and the list an
    agent queries while authoring. One list, so a bundle cannot offer a language
    the lint rejects or lack one it accepts. Add a language there, then rerun the
    bundles that read this.
    """
    return json.loads((ASSETS / "registry.json").read_text(encoding="utf-8"))[
        "$languages"
    ]["names"]


# Where leaf's name for a language differs from highlight.js's module. Every
# other name maps to itself.
HLJS_ALIASES = {"html": "xml", "toml": "ini"}


def build_highlight(work: Path) -> list[Path]:
    """highlight.js colors a page's code blocks. Upstream ships no
    browser-native ESM build — the `es/` directory re-exports CommonJS and only
    resolves through a bundler — so the vendored file is one we produce: core
    plus exactly the languages the registry enumerates, bundled to ESM and
    minified.

    Each language registers under leaf's own name (`html`, not hljs's `xml`), so
    the page's vocabulary and the tokenizer's cannot drift: `language="html"`
    either resolves or the bundle was built from a different list than the
    registry states.
    """
    out = ASSETS / "vendor/highlight.esm.js"
    # Core is the CommonJS build, which the package's exports map offers only to
    # `require`, so it is imported by path.
    package = (NODE_MODULES / "highlight.js").as_posix()
    names = languages()
    entry = [
        (
            f"/*! highlight.js {version('highlight.js')} — BSD-3-Clause"
            " — https://highlightjs.org */"
        ),
        f'import hljs from "{package}/lib/core.js";',
        *(
            f"import {name} from"
            f' "highlight.js/lib/languages/{HLJS_ALIASES.get(name, name)}";'
            for name in names
        ),
        # Registered under leaf's name, not highlight.js's, so `language="html"`
        # resolves without a translation table living anywhere at runtime.
        *(f'hljs.registerLanguage("{name}", {name});' for name in names),
        "export default hljs;",
    ]
    (work / "entry.mjs").write_text("\n".join(entry) + "\n", encoding="utf-8")
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--minify",
        "--legal-comments=inline",
        f"--outfile={out}",
        cwd=work,
    )
    return [out]


def build_jsdiff(work: Path) -> list[Path]:
    """Bundle only jsdiff's array comparison for the core browser runtime."""
    out = ASSETS / "vendor/jsdiff.esm.js"
    (work / "entry.mjs").write_text(
        (
            f"/*! jsdiff {version('diff')} — BSD-3-Clause"
            " — https://github.com/kpdecker/jsdiff */\n"
            'export { diffArrays } from "diff/lib/diff/array.js";\n'
        ),
        encoding="utf-8",
    )
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--minify",
        "--legal-comments=inline",
        f"--outfile={out}",
        cwd=work,
    )
    return [out]


def refuse_if_csp_forbids(out: Path) -> None:
    """Delete the bundle and stop, if it carries something the page cannot run.

    The interactive export's CSP admits neither eval nor a chunk it did not
    embed, and both of those are one careless import away: d3 carries a
    `new Function` in d3-dsv's CSV parser, and Plot reaches for none of d3-dsv
    today. What keeps that true is this check rather than anyone remembering,
    because the failure it prevents is a chart that draws in a developer's page
    and refuses in a user's.

    Bundles call this when their inputs contain no grammar or other data that can
    legitimately carry these strings. Pierre does not: its TextMate grammars contain
    the literal `import(` as data and would be refused wrongly.
    """
    text = out.read_text(encoding="utf-8")
    for banned in ("new Function", "eval(", "import("):
        if banned in text:
            out.unlink()
            sys.exit(
                f"refused: the bundle contains {banned}, which the page CSP forbids"
            )


def package_notices(packages: tuple[str, ...], title: str) -> str:
    """The licenses for the packages a build names as reaching its bundle."""
    notices = []
    for package in packages:
        root = NODE_MODULES / package
        manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
        license_file = next(
            (
                path
                for path in root.iterdir()
                if path.is_file()
                and path.name.lower().split(".", 1)[0]
                in {"license", "licence", "copying"}
            ),
            None,
        )
        if license_file is None:
            raise RuntimeError(f"no license file shipped by {manifest['name']}")
        notices.append(
            f"===== {manifest['name']} {manifest['version']} "
            f"({manifest['license']}) =====\n"
            f"{license_file.read_text(encoding='utf-8').strip()}"
        )
    return f"Third-party licenses for {title}\n\n" + "\n\n".join(notices) + "\n"


def build_agentic_mermaid(work: Path) -> list[Path]:
    """Bundle Agentic Mermaid's SVG renderer and ELK into one browser-native ESM file.

    Upstream's ESM keeps `entities`, `elkjs` and `yaml` as bare imports. Leaf loads one
    self-contained file under its self-only CSP, so esbuild resolves the locked
    dependency set and leaves no runtime chunk or package lookup behind. The package
    entry also exports PNG, CLI and agent tooling; importing only `renderMermaidSVG`
    keeps the native rasterizer and the code-mode parser out of the bundle.

    The renderer carries Material Design Icons path data for architecture diagrams
    under Apache-2.0. Its `THIRD_PARTY_NOTICES.md` says what that covers and its own
    `LICENSES/` holds the text, so the notices take both.
    """
    out = package_vendor("diagram") / "agentic-mermaid.esm.js"
    notices = package_vendor("diagram") / "agentic-mermaid.LICENSES.txt"
    packages = ("agentic-mermaid", "elkjs", "entities", "yaml")
    (work / "entry.mjs").write_text(
        'export { renderMermaidSVG } from "agentic-mermaid";\n',
        encoding="utf-8",
    )
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--platform=browser",
        "--target=chrome105",
        "--minify",
        "--legal-comments=inline",
        f"--banner:js=/*! agentic-mermaid {version('agentic-mermaid')} — MIT"
        " — licenses: agentic-mermaid.LICENSES.txt */",
        f"--outfile={out}",
        cwd=work,
    )
    refuse_if_csp_forbids(out)
    renderer = NODE_MODULES / "agentic-mermaid"
    bundled = [
        renderer / "THIRD_PARTY_NOTICES.md",
        *sorted(renderer.glob("LICENSES/*")),
    ]
    notices.write_text(
        package_notices(packages, out.name)
        + "".join(
            f"\n===== agentic-mermaid: {path.relative_to(renderer)} =====\n"
            f"{path.read_text(encoding='utf-8').strip()}\n"
            for path in bundled
        ),
        encoding="utf-8",
    )
    return [out, notices]


def build_floating_ui(work: Path) -> list[Path]:
    """Bundle the browser's anchored-positioning primitive.

    Floating UI's DOM package publishes browser ESM, but leaves its core and utility
    packages as bare imports. Leaf pages run under a self-only CSP and have no package
    resolver, so the three packages become one browser-native module. Only the
    positioning and lifecycle middleware used by Leaf's floating chrome are exported;
    esbuild drops the rest.
    """
    out = ASSETS / "vendor/floating-ui.esm.js"
    notices = ASSETS / "vendor/floating-ui.LICENSES.txt"
    packages = ("@floating-ui/dom", "@floating-ui/core", "@floating-ui/utils")
    (work / "entry.mjs").write_text(
        "export { autoUpdate, computePosition, flip, limitShift, offset, shift, size } "
        'from "@floating-ui/dom";\n',
        encoding="utf-8",
    )
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--platform=browser",
        "--target=chrome105",
        "--minify",
        "--legal-comments=inline",
        f"--banner:js=/*! @floating-ui/dom {version('@floating-ui/dom')} — MIT"
        " — licenses: floating-ui.LICENSES.txt */",
        f"--outfile={out}",
        cwd=work,
    )
    refuse_if_csp_forbids(out)
    notices.write_text(package_notices(packages, out.name), encoding="utf-8")
    return [out, notices]


def build_webawesome(work: Path) -> list[Path]:
    """Split chrome controls from optional widgets, sharing their dependency graph.

    Both entry points register the same components once. Optional controls remain
    on demand; the shared chunks are core payload because chrome also reads them.

    Lit is not bundled: every Lit import binds to `/vendor/lit.js`, the page's one
    copy, which `scripts/browser/build.mjs` builds from the same install. Where that
    Lit falls outside Web Awesome's declared range, npm nests Web Awesome's own
    choice under the package, and the build refuses rather than run Web Awesome
    against a Lit it was not published for.
    """
    directory = package_vendor("default")
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / "webawesome.esm.js"
    notices = directory / "webawesome.LICENSES.txt"
    packages = (
        "@awesome.me/webawesome",
        "@ctrl/tinycolor",
        "@shoelace-style/localize",
        "composed-offset-position",
        "nanoid",
        "@floating-ui/dom",
        "@floating-ui/core",
        "@floating-ui/utils",
    )
    if (NODE_MODULES / "@awesome.me/webawesome/node_modules/lit").exists():
        raise RuntimeError(
            f"Web Awesome's declared Lit range excludes lit {version('lit')}"
        )
    source = ROOT / "scripts/vendor-src/webawesome"
    for name in ("entry.mjs", "chrome.mjs", "setup.mjs", "build.mjs", "leaf-theme.css"):
        shutil.copyfile(source / name, work / name)
    run(
        "node",
        "build.mjs",
        str(work / "bundle"),
        version("@awesome.me/webawesome"),
        cwd=work,
    )
    consumed = tuple(json.loads((work / "packages.json").read_text()))
    if set(consumed) != set(packages):
        raise RuntimeError(f"Web Awesome runtime dependencies changed: {consumed}")
    shared = ASSETS / "vendor/webawesome"
    if shared.exists():
        shutil.rmtree(shared)
    shutil.copytree(work / "bundle/webawesome", shared)
    shutil.copyfile(work / "bundle/webawesome.esm.js", out)
    chrome = ASSETS / "vendor/webawesome-chrome.js"
    shutil.copyfile(work / "bundle/webawesome-chrome.js", chrome)
    outputs = [out, chrome, *sorted(shared.glob("*.js"))]
    for output in outputs:
        refuse_if_csp_forbids(output)
    notices.write_text(package_notices(consumed, out.name), encoding="utf-8")
    return [*outputs, notices]


def build_plot(work: Path) -> list[Path]:
    """Observable Plot draws lf-chart. Nothing published is loadable as it
    stands, and there are three things to try: `src/index.js` is browser-native
    ESM but imports d3 by bare specifier; `dist/plot.umd.min.js` leaves d3
    external too, reading a `d3` global the page would have to have loaded first;
    and a CDN's prebuilt ESM (jsdelivr's `+esm`) is smaller than this bundle only
    because it imports d3 from a second URL, while the layer loads nothing from
    the network so a chart draws offline and in an export. So the vendored file
    is one we produce, the same way highlight.js's is: Plot and the parts of d3 it reaches for, bundled to one browser-native
    ESM file with no specifier left in it. The alternative is vendoring d3 whole
    beside it, which is 100KB more and two files whose versions can drift apart.

    The whole of Plot goes in rather than the marks lf-chart happens to use
    today. Naming the marks here would put the module's mark list in a second
    place, where a chart kind added in the module renders as a TypeError instead;
    the list is worth about 100KB, against a 385KB bundle.
    """
    out = package_vendor("default") / "plot.esm.js"
    (work / "entry.mjs").write_text(
        'export * from "@observablehq/plot";\n', encoding="utf-8"
    )
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--minify",
        "--legal-comments=inline",
        f"--banner:js=/*! @observablehq/plot {version('@observablehq/plot')} — ISC"
        " — https://observablehq.com/plot\n"
        f" *  bundled with d3 {version('d3')} — ISC — https://d3js.org */",
        f"--outfile={out}",
        cwd=work,
    )
    refuse_if_csp_forbids(out)
    return [out]


PIERRE_LANGUAGE_SENTINEL = "/* LEAF_PIERRE_LANGUAGES */"


def build_pierre(work: Path) -> list[Path]:
    """Pierre and Shiki expose far more languages and themes than Leaf declares,
    so this bundle carries only the grammars the registry names plus the two
    fixed token themes lf-diff maps onto Leaf's syntax roles.

    `vendor-src/pierre/shiki-leaf.mjs` holds exactly one `LEAF_PIERRE_LANGUAGES`
    sentinel, which this replaces with a dynamic import for each registry language.
    """
    out = package_vendor("diff") / "pierre-diffs.esm.js"
    notices = package_vendor("diff") / "pierre-diffs.LICENSES.txt"
    shiki_source = (PIERRE_SOURCE / "shiki-leaf.mjs").read_text(encoding="utf-8")
    if shiki_source.count(PIERRE_LANGUAGE_SENTINEL) != 1:
        raise RuntimeError("Pierre's Shiki source must contain one language sentinel")
    (work / "shiki-leaf.mjs").write_text(
        shiki_source.replace(
            PIERRE_LANGUAGE_SENTINEL,
            "\n"
            + "\n".join(
                f'  "{name}": () => import("@shikijs/langs/{name}"),'
                for name in languages()
            )
            + "\n",
        ),
        encoding="utf-8",
    )
    for name in ("themes-leaf.mjs", "entry.mjs", "build.mjs"):
        shutil.copyfile(PIERRE_SOURCE / name, work / name)
    run(
        "node",
        "build.mjs",
        str(out),
        str(notices),
        version("@pierre/diffs"),
        cwd=work,
    )
    return [out, notices]


def build_mcp_app(work: Path) -> list[Path]:
    """Bundle the adaptive MCP App into one self-contained `ui://` resource.

    An MCP host reads one HTML blob from the server; it does not fetch Leaf's
    ordinary app assets. The SDK, application code, styles, and existing Leaf
    mark are therefore inlined into committed files that an installed plugin can
    serve without npm or network access. A complete-page result may frame the
    process-scoped page server, while a snapshot result stays inside the same
    standalone resource.
    """
    source = ROOT / "scripts/mcp-app"
    entry = work / "page-entry.js"
    bundle = work / "page-bundle.js"
    out = MCP_APP / "page-app.html"
    shutil.copyfile(source / "page-app.js", entry)
    esbuild(
        entry.name,
        "--bundle",
        "--format=iife",
        "--platform=browser",
        "--target=chrome105",
        "--minify",
        "--legal-comments=inline",
        f"--banner:js=/*! @modelcontextprotocol/ext-apps {version('@modelcontextprotocol/ext-apps')}"
        " — MIT — https://github.com/modelcontextprotocol/ext-apps */",
        f"--outfile={bundle}",
        cwd=work,
    )
    html = (source / "page-app.html").read_text(encoding="utf-8")
    html = html.replace(
        "/* LEAF_MCP_STYLE */",
        (source / "page-app.css").read_text(encoding="utf-8").strip(),
    )
    html = html.replace(
        "/* LEAF_MCP_SCRIPT */",
        bundle.read_text(encoding="utf-8").strip().replace("</script", "<\\/script"),
    )
    html = html.replace(
        "<!-- LEAF_MCP_ICON -->",
        (ASSETS / "icon.svg").read_text(encoding="utf-8").strip(),
    )
    out.write_text(html, encoding="utf-8")
    return [out]


BUILDS: dict[str, Callable[[Path], list[Path]]] = {
    "agentic-mermaid": build_agentic_mermaid,
    "floating-ui": build_floating_ui,
    "highlight": build_highlight,
    "jsdiff": build_jsdiff,
    "mcp-app": build_mcp_app,
    "plot": build_plot,
    "pierre": build_pierre,
    "webawesome": build_webawesome,
}


def vendor(name: str) -> list[Path]:
    if name in COPIES:
        copy = COPIES[name]
        shutil.copyfile(NODE_MODULES / copy.package / copy.inside, copy.out)
        return [copy.out]
    # Under the root, so a bare import in an entry, and in a build script that imports
    # esbuild, resolves the way Node's does: up to the root `node_modules`.
    scratch = ROOT / ".tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="vendor-") as tmp:
        return BUILDS[name](Path(tmp))


def main() -> None:
    known = sorted(COPIES | BUILDS)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bundle", nargs="*", help=f"one or more of: {', '.join(known)}")
    args = parser.parse_args()

    unknown = sorted(set(args.bundle) - set(known))
    if unknown:
        parser.error(f"unknown bundle: {', '.join(unknown)}")
    for name in args.bundle or known:
        for out in vendor(name):
            print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
