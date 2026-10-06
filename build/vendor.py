#!/usr/bin/env python3
"""Rebuild the third-party bundles Leaf ships.

Nothing builds them at install time, so they are tracked. The files under
`skills/leaf/assets/vendor/` and each package's own `vendor/` are page payload:
`page init` copies them into a page directory and a user's browser runs them.

They arrive two ways, which is the shape of this file. Where upstream already
publishes a file a browser can load, vendoring is three values — the package,
the file inside it, and where it lands — so those are rows in COPIES. Where
nothing published is loadable as it stands, or what Leaf ships is cut down to
what its registry declares, vendoring is a program, so those are functions.
Either way, what comes out passes through `build/browser/shipped.mjs`, the
owner `build/browser/build.mjs` shares: it refuses a module an export cannot
load and writes the bundle's license notices (`vendor`).

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
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills/leaf/assets"
PACKAGES = ROOT / "skills/leaf/packages"
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
    """Bundle, recording in the work directory's `meta.json` what the bundle read."""
    run(str(NODE_MODULES / ".bin/esbuild"), *args, "--metafile=meta.json", cwd=cwd)


def languages() -> list[str]:
    """The language names a bundle is cut to.

    They are read out of registry.json rather than stated here, because that is
    the list `page check` refuses an unknown language against and the list an
    agent queries while authoring. One list, so a bundle cannot offer a language
    the lint rejects or lack one it accepts. Add a language there, then rerun the
    bundles that read this.
    """
    return json.loads((ASSETS / "registry.json").read_text(encoding="utf-8"))[
        "$languages"
    ]["names"]


def build_syntax(work: Path) -> list[Path]:
    """Share one Shiki engine between code blocks and Pierre, loading grammars
    only for languages the page draws. Static imports share embedded grammars;
    the generated runtime loader map names the registry's language entry points.
    """
    source = ROOT / "build/syntax"
    for name in ("entry.mjs", "build.mjs"):
        shutil.copyfile(source / name, work / name)
    run(
        "node",
        "build.mjs",
        str(work / "bundle"),
        str(ASSETS / "registry.json"),
        cwd=work,
    )
    directory = ASSETS / "vendor/syntax"
    if directory.exists():
        shutil.rmtree(directory)
    shutil.copytree(work / "bundle/syntax", directory)
    out = ASSETS / "vendor/syntax.esm.js"
    shutil.copyfile(work / "bundle/syntax.esm.js", out)
    (ASSETS / "runtime/syntax-languages.js").write_text(
        "// Generated by build/vendor.py from registry.json's $languages.names.\n"
        "// prettier-ignore\n"
        "export const syntaxLanguages = {\n"
        + "".join(
            f'  "{name}": () => import("/vendor/syntax/{name}.js"),\n'
            for name in languages()
        )
        + "};\n",
        encoding="utf-8",
    )
    return [out, *sorted(directory.glob("*.js"))]


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


def build_codemirror(work: Path) -> list[Path]:
    """CodeMirror 6 is the editor inside every runtime composer (`leaf-text`).

    One bundle holds the editor core and the GFM Markdown language, exporting
    exactly the names `composing/text-field.js` imports. The runtime owns the
    live-preview decorations; nothing here styles a document. The language comes
    without `markdown()`, whose HTML-block support would carry the HTML, CSS and
    JavaScript grammars into the bundle for syntax a comment never highlights.
    """
    out = ASSETS / "vendor/codemirror.esm.js"
    (work / "entry.mjs").write_text(
        (
            f"/*! CodeMirror {version('@codemirror/view')} — MIT"
            " — https://codemirror.net */\n"
            'export { EditorView, keymap, Decoration, ViewPlugin } from "@codemirror/view";\n'
            'export { EditorState, Compartment } from "@codemirror/state";\n'
            "export { history, standardKeymap, historyKeymap }"
            ' from "@codemirror/commands";\n'
            'export { LanguageSupport } from "@codemirror/language";\n'
            "export { markdownLanguage, insertNewlineContinueMarkup }"
            ' from "@codemirror/lang-markdown";\n'
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


def build_agentic_mermaid(work: Path) -> list[Path]:
    """Bundle Agentic Mermaid's SVG renderer and ELK into one browser-native ESM file.

    Upstream's ESM keeps `entities`, `elkjs` and `yaml` as bare imports. Leaf pages have no
    package resolver and load one self-contained file, so esbuild resolves the locked
    dependency set and leaves no runtime chunk or package lookup behind. The package
    entry also exports PNG, CLI and agent tooling; importing only `renderMermaidSVG`
    keeps the native rasterizer and the code-mode parser out of the bundle.

    The renderer carries Material Design Icons path data for architecture diagrams
    under Apache-2.0, which its `THIRD_PARTY_NOTICES.md` and `LICENSES/` pass on.
    """
    out = package_vendor("diagram") / "agentic-mermaid.esm.js"
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
    return [out]


def build_floating_ui(work: Path) -> list[Path]:
    """Bundle the browser's anchored-positioning primitive.

    Floating UI's DOM package publishes browser ESM, but leaves its core and utility
    packages as bare imports. Leaf pages have no package resolver,
    so the three packages become one browser-native module. Only the
    positioning and lifecycle middleware used by Leaf's floating chrome are exported;
    esbuild drops the rest.
    """
    out = ASSETS / "vendor/floating-ui.esm.js"
    (work / "entry.mjs").write_text(
        "export { autoUpdate, getOverflowAncestors, computePosition, flip, limitShift, offset, shift, size } "
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
    return [out]


def build_webawesome(work: Path) -> list[Path]:
    """Split chrome controls from optional widgets, sharing their dependency graph.

    Both entry points register the same components once. Optional controls remain
    on demand; the shared chunks are core payload because chrome also reads them.

    Lit is not bundled: every Lit import binds to `/vendor/lit.js`, the page's one
    copy, which `build/browser/build.mjs` builds from the same install. Where that
    Lit falls outside Web Awesome's declared range, npm nests Web Awesome's own
    choice under the package, and the build refuses rather than run Web Awesome
    against a Lit it was not published for.
    """
    directory = package_vendor("default")
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / "webawesome.esm.js"
    if (NODE_MODULES / "@awesome.me/webawesome/node_modules/lit").exists():
        raise RuntimeError(
            f"Web Awesome's declared Lit range excludes lit {version('lit')}"
        )
    source = ROOT / "build/webawesome"
    for name in ("entry.mjs", "chrome.mjs", "build.mjs", "leaf-theme.css"):
        shutil.copyfile(source / name, work / name)
    run(
        "node",
        "build.mjs",
        str(work / "bundle"),
        version("@awesome.me/webawesome"),
        cwd=work,
    )
    shared = ASSETS / "vendor/webawesome"
    if shared.exists():
        shutil.rmtree(shared)
    shutil.copytree(work / "bundle/webawesome", shared)
    shutil.copyfile(work / "bundle/webawesome.esm.js", out)
    chrome = ASSETS / "vendor/webawesome-chrome.js"
    shutil.copyfile(work / "bundle/webawesome-chrome.js", chrome)
    return [out, chrome, *sorted(shared.glob("*.js"))]


def build_plot(work: Path) -> list[Path]:
    """Observable Plot, which lf-chart hands a page's author. Nothing published is loadable as it
    stands, and there are three things to try: `src/index.js` is browser-native
    ESM but imports d3 by bare specifier; `dist/plot.umd.min.js` leaves d3
    external too, reading a `d3` global the page would have to have loaded first;
    and a CDN's prebuilt ESM (jsdelivr's `+esm`) is smaller than this bundle only
    because it imports d3 from a second URL, while the layer loads nothing from
    the network so a chart draws offline and in an export. So the vendored file
    is one we produce: Plot and the parts of d3 it reaches for, bundled to one browser-native
    ESM file with no specifier left in it. The alternative is vendoring d3 whole
    beside it, which is 100KB more and two files whose versions can drift apart.

    The whole of Plot goes in, since an author writes the chart in Plot's own API
    and may reach for any of it.
    """
    out = package_vendor("default") / "plot.esm.js"
    (work / "entry.mjs").write_text(
        'export * from "@observablehq/plot";\n',
        encoding="utf-8",
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
    return [out]


def build_pierre(work: Path) -> list[Path]:
    """Bundle Pierre's static renderer against the shared Leaf syntax engine."""
    out = package_vendor("diff") / "pierre-diffs.esm.js"
    source = ROOT / "build/pierre"
    for name in ("themes-leaf.mjs", "wasm-leaf.mjs", "entry.mjs", "build.mjs"):
        shutil.copyfile(source / name, work / name)
    run("node", "build.mjs", str(out), version("@pierre/diffs"), cwd=work)
    return [out]


BUILDS: dict[str, Callable[[Path], list[Path]]] = {
    "agentic-mermaid": build_agentic_mermaid,
    "codemirror": build_codemirror,
    "floating-ui": build_floating_ui,
    "syntax": build_syntax,
    "jsdiff": build_jsdiff,
    "plot": build_plot,
    "pierre": build_pierre,
    "webawesome": build_webawesome,
}


def copy_published(copy: Copy, work: Path) -> list[Path]:
    """Take a published file as it stands, recorded as esbuild would record it: one
    output whose every byte came from the one input."""
    source = NODE_MODULES / copy.package / copy.inside
    shutil.copyfile(source, copy.out)
    size = copy.out.stat().st_size
    meta = {
        "outputs": {str(copy.out): {"inputs": {str(source): {"bytesInOutput": size}}}}
    }
    (work / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return [copy.out]


def vendor(name: str) -> list[Path]:
    """Make one bundle, then pass it through `build/browser/shipped.mjs`.

    That module owns what a committed bundle must be and carry: it refuses a module
    an export cannot load, and writes `<bundle>.LICENSES.txt` from the packages the
    build's `meta.json` says reached it.
    """
    # Under the root, so a bare import in an entry, and in a build script that imports
    # esbuild, resolves the way Node's does: up to the root `node_modules`.
    scratch = ROOT / ".tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="vendor-") as tmp:
        work = Path(tmp)
        outputs = (
            copy_published(COPIES[name], work) if name in COPIES else BUILDS[name](work)
        )
        first = outputs[0]
        notices = first.with_name(f"{first.name.split('.')[0]}.LICENSES.txt")
        run(
            "node",
            str(ROOT / "build/browser/shipped.mjs"),
            "meta.json",
            str(notices),
            *(str(output) for output in outputs if output.suffix == ".js"),
            cwd=work,
        )
        return [*outputs, notices]


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
