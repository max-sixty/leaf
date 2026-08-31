#!/usr/bin/env python3
"""Rebuild the third-party bundles a Leaf page loads.

The tracked files under `skills/leaf/assets/vendor/` and
`skills/leaf/packages/default/vendor/` are payload: a page vendors them and a
reader's browser runs them, and nothing builds them at install time.

They arrive two ways, which is the shape of this file. Where upstream already
publishes a file a browser can load, vendoring is three values — the package,
the file inside it, and where it lands — so those are rows in COPIES. Where
nothing published is loadable as it stands, or what Leaf ships is cut down to
what its registry declares, vendoring is a program, so those are functions.

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
PACKAGE_VENDOR = ROOT / "skills/leaf/packages/default/vendor"

# Every pinned version, exact and in one place. A range would let a dependency
# move under a bundle nobody rebuilt, and then the tracked bytes stop being what
# this file produces. `esbuild` is the tool the three builds share rather than
# payload, so it moves when a bundle needs it rather than on every release.
PINS = {
    "highlight.js": "11.12.0",
    "marked": "18.0.11",
    "mermaid": "11.17.2",
    "sortablejs": "1.15.7",
    "@observablehq/plot": "0.6.17",
    "@pierre/diffs": "1.3.6",
    "@modelcontextprotocol/ext-apps": "1.7.5",
    "shiki": "4.4.3",
    "esbuild": "0.28.2",
}


def spec(package: str) -> str:
    return f"{package}@{PINS[package]}"


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
    # lf-diagram loads mermaid through a `<script src>` tag and reads
    # `globalThis.mermaid`, so this is the IIFE build that defines that global —
    # the ESM entry defines none, and the widget imports no modules. mermaid
    # publishes its dependencies already built in, so there is nothing to bundle.
    #
    # lf-diagram addresses a commentable box by the id mermaid draws it under,
    # and that scheme has moved between minor versions. Run
    # tests/test_render_aim.py against a new one.
    "mermaid": Copy(
        "mermaid", "dist/mermaid.min.js", PACKAGE_VENDOR / "mermaid.min.js"
    ),
    # SortableJS drags lf-board's cards. The package ships its ESM entry three
    # times over, carrying the same plugin code each time and differing only in
    # which plugins it mounts, so the choice costs no bytes. This is the `module`
    # entry, which mounts the autoscroll that lf-board's `scroll` option drives.
    # `sortable.core.esm.js` mounts nothing and would drop that autoscroll;
    # `sortable.complete.esm.js` mounts swap and multi-drag on top, and lf-board
    # sets neither.
    "sortable": Copy(
        "sortablejs", "modular/sortable.esm.js", PACKAGE_VENDOR / "sortable.esm.js"
    ),
}


def run(*args: str, cwd: Path, capture: bool = False) -> str:
    done = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return (done.stdout or "").strip()


def unpack(package: str, work: Path) -> Path:
    """Unpack a published package into work/package, and answer that directory."""
    tarball = run("npm", "pack", "--silent", spec(package), cwd=work, capture=True)
    run("tar", "xzf", tarball, cwd=work)
    return work / "package"


def esbuild(*args: str, cwd: Path) -> None:
    run("npx", "--yes", spec("esbuild"), *args, cwd=cwd)


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
    unpack("highlight.js", work)
    names = languages()
    entry = [
        (
            f"/*! highlight.js {PINS['highlight.js']} — BSD-3-Clause"
            " — https://highlightjs.org */"
        ),
        'import hljs from "./package/lib/core.js";',
        *(
            f"import {name} from"
            f' "./package/es/languages/{HLJS_ALIASES.get(name, name)}.js";'
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


def refuse_if_csp_forbids(out: Path) -> None:
    """Delete the bundle and stop, if it carries something the page cannot run.

    A page's CSP is `default-src 'self'`, which allows neither eval nor a lazy
    chunk, and both of those are one careless import away: d3 carries a
    `new Function` in d3-dsv's CSV parser, and Plot reaches for none of d3-dsv
    today. What keeps that true is this check rather than anyone remembering,
    because the failure it prevents is a chart that draws in a developer's page
    and refuses in a reader's.

    Only Plot's bundle is checked. This is a substring search, so it cannot
    tell code from data, and pierre's carries the literal `import(` inside
    TextMate grammars, where it is data and would be refused wrongly.
    """
    text = out.read_text(encoding="utf-8")
    for banned in ("new Function", "eval(", "import("):
        if banned in text:
            out.unlink()
            sys.exit(
                f"refused: the bundle contains {banned}, which the page CSP forbids"
            )


def build_plot(work: Path) -> list[Path]:
    """Observable Plot draws lf-chart. Nothing published is loadable as it
    stands, and there are three things to try: `src/index.js` is browser-native
    ESM but imports d3 by bare specifier; `dist/plot.umd.min.js` leaves d3
    external too, reading a `d3` global the page would have to have loaded first;
    and a CDN's prebuilt ESM (jsdelivr's `+esm`) is smaller than this bundle only
    because it imports d3 from a second URL, which `default-src 'self'` will not
    fetch. So the vendored file is one we produce, the same way highlight.js's
    is: Plot and the parts of d3 it reaches for, bundled to one browser-native
    ESM file with no specifier left in it. The alternative is vendoring d3 whole
    beside it, which is 100KB more and two files whose versions can drift apart.

    The whole of Plot goes in rather than the marks lf-chart happens to use
    today. Naming the marks here would put the module's mark list in a second
    place, where a chart kind added in the module renders as a TypeError instead;
    the list is worth about 100KB, against a payload whose mermaid bundle is
    3.4MB.
    """
    out = PACKAGE_VENDOR / "plot.esm.js"
    run(
        "npm",
        "install",
        "--silent",
        "--no-audit",
        "--no-fund",
        spec("@observablehq/plot"),
        cwd=work,
        capture=True,
    )
    d3 = run(
        "node",
        "-p",
        "require('./node_modules/d3/package.json').version",
        cwd=work,
        capture=True,
    )
    (work / "entry.mjs").write_text(
        'export * from "@observablehq/plot";\n', encoding="utf-8"
    )
    esbuild(
        "entry.mjs",
        "--bundle",
        "--format=esm",
        "--minify",
        "--legal-comments=inline",
        f"--banner:js=/*! @observablehq/plot {PINS['@observablehq/plot']} — ISC"
        " — https://observablehq.com/plot\n"
        f" *  bundled with d3 {d3} — ISC — https://d3js.org */",
        f"--outfile={out}",
        cwd=work,
    )
    refuse_if_csp_forbids(out)
    return [out]


# Shiki's public entry, cut to the languages the registry declares and to the
# JavaScript regex engine. The oniguruma engine loads WebAssembly, which
# `default-src 'self'` will not fetch.
PIERRE_SHIKI = """\
import {{
  createBundledHighlighter,
  createCssVariablesTheme,
  createSingletonShorthands,
  getTokenStyleObject,
  stringifyTokenStyle,
}} from "@shikijs/core";
import {{ createJavaScriptRegexEngine }} from "@shikijs/engine-javascript";

export const bundledLanguages = {{
{languages}
}};

export const createHighlighter = createBundledHighlighter({{
  langs: bundledLanguages,
  themes: {{}},
  engine: createJavaScriptRegexEngine,
}});
export const {{ codeToHtml }} = createSingletonShorthands(createHighlighter);
export {{
  createCssVariablesTheme,
  createJavaScriptRegexEngine,
  getTokenStyleObject,
  stringifyTokenStyle,
}};
export const createOnigurumaEngine = () => {{
  throw new Error("Leaf's Pierre bundle includes the JavaScript regex engine only");
}};
"""

# Pierre's theme registry, cut to the two token themes lf-diff maps onto Leaf's
# syntax roles.
PIERRE_THEMES = """\
import { normalizeTheme } from "@shikijs/core";

const descriptors = new Map([
  ["github-light", {
    name: "github-light",
    load: () => import("@shikijs/themes/github-light"),
  }],
  ["github-dark", {
    name: "github-dark",
    load: () => import("@shikijs/themes/github-dark"),
  }],
]);

export const createTheme = ({ name, load, ...metadata }) => ({
  name,
  ...metadata,
  load: async () => {
    const loaded = await load();
    return normalizeTheme(loaded?.default ?? loaded);
  },
});
export const pierreThemes = { getThemes: () => [] };
export const shikiThemes = { getTheme: (name) => descriptors.get(name) };
"""

PIERRE_ENTRY = """\
export { parsePatchFiles } from "@pierre/diffs";
export { preloadDiffHTML } from "@pierre/diffs/ssr";
"""

# esbuild resolves `shiki` and Pierre's theme registry onto the two shims above,
# then every package that reached the bundle is read back out of the metafile so
# its license ships beside it.
PIERRE_BUILD = """\
import fs from "node:fs";
import path from "node:path";
import { build } from "esbuild";

const work = process.cwd();
const result = await build({
  entryPoints: [path.join(work, "entry.mjs")],
  outfile: process.argv[2],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "chrome105",
  minify: true,
  legalComments: "inline",
  banner: {
    js: `/*! @pierre/diffs ${process.argv[4]} — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */`,
  },
  plugins: [{
    name: "leaf-pierre-bounds",
    setup(build) {
      build.onResolve({ filter: /^shiki$/ }, () => ({
        path: path.join(work, "shiki-leaf.mjs"),
      }));
      build.onResolve({ filter: /^@pierre\\/theming\\/themes$/ }, () => ({
        path: path.join(work, "themes-leaf.mjs"),
      }));
    },
  }],
  metafile: true,
});

const packageRoots = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  const relative = input.split("node_modules/").at(-1);
  if (relative === input) continue;
  const parts = relative.split("/");
  packageRoots.add(path.join(
    work,
    "node_modules",
    ...(parts[0].startsWith("@") ? parts.slice(0, 2) : parts.slice(0, 1)),
  ));
}
const notices = [...packageRoots].sort().map((root) => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json")));
  const licenseFile = fs.readdirSync(root).find((name) =>
    /^(licen[cs]e|copying)(\\.|$)/i.test(name)
  );
  if (licenseFile == null)
    throw new Error(`No license file shipped by ${manifest.name}`);
  return [
    `===== ${manifest.name} ${manifest.version} (${manifest.license}) =====`,
    fs.readFileSync(path.join(root, licenseFile), "utf8").trim(),
  ].join("\\n");
});
fs.writeFileSync(
  process.argv[3],
  "Third-party licenses for pierre-diffs.esm.js\\n\\n" + notices.join("\\n\\n") + "\\n",
);
"""


def build_pierre(work: Path) -> list[Path]:
    """Pierre and Shiki expose far more languages and themes than Leaf declares,
    so this bundle carries only the grammars the registry names plus the two
    fixed token themes lf-diff maps onto Leaf's syntax roles.
    """
    out = PACKAGE_VENDOR / "pierre-diffs.esm.js"
    notices = PACKAGE_VENDOR / "pierre-diffs.LICENSES.txt"
    shiki = PINS["shiki"]
    run(
        "npm",
        "install",
        "--no-save",
        "--no-package-lock",
        "--silent",
        spec("@pierre/diffs"),
        spec("shiki"),
        f"@shikijs/core@{shiki}",
        f"@shikijs/engine-javascript@{shiki}",
        f"@shikijs/langs@{shiki}",
        f"@shikijs/themes@{shiki}",
        spec("esbuild"),
        cwd=work,
    )
    (work / "shiki-leaf.mjs").write_text(
        PIERRE_SHIKI.format(
            languages="\n".join(
                f'  "{name}": () => import("@shikijs/langs/{name}"),'
                for name in languages()
            )
        ),
        encoding="utf-8",
    )
    (work / "themes-leaf.mjs").write_text(PIERRE_THEMES, encoding="utf-8")
    (work / "entry.mjs").write_text(PIERRE_ENTRY, encoding="utf-8")
    (work / "build.mjs").write_text(PIERRE_BUILD, encoding="utf-8")
    run(
        "node",
        "build.mjs",
        str(out),
        str(notices),
        PINS["@pierre/diffs"],
        cwd=work,
    )
    return [out, notices]


def build_mcp_app(work: Path) -> list[Path]:
    """Bundle the MCP Apps surfaces into self-contained `ui://` resources.

    An MCP host reads one HTML blob from the server; it does not fetch Leaf's
    ordinary app assets. The SDK, application code, styles, and existing Leaf
    mark are therefore inlined into committed files that an installed plugin can
    serve without npm or network access. The complete-page resource may frame
    the process-scoped page server, but the resource itself remains standalone.
    """
    source = ROOT / "scripts/mcp-app"
    run(
        "npm",
        "install",
        "--no-save",
        "--no-package-lock",
        "--silent",
        spec("@modelcontextprotocol/ext-apps"),
        spec("esbuild"),
        cwd=work,
    )
    outputs = []
    for name in ("compact", "page"):
        entry = work / f"{name}-entry.js"
        bundle = work / f"{name}-bundle.js"
        out = ASSETS / f"vendor/mcp-{name}-app.html"
        shutil.copyfile(source / f"{name}-app.js", entry)
        esbuild(
            entry.name,
            "--bundle",
            "--format=iife",
            "--platform=browser",
            "--target=chrome105",
            "--minify",
            "--legal-comments=inline",
            f"--banner:js=/*! @modelcontextprotocol/ext-apps {PINS['@modelcontextprotocol/ext-apps']}"
            " — MIT — https://github.com/modelcontextprotocol/ext-apps */",
            f"--outfile={bundle}",
            cwd=work,
        )
        html = (source / f"{name}-app.html").read_text(encoding="utf-8")
        html = html.replace(
            "/* LEAF_MCP_STYLE */",
            (source / f"{name}-app.css").read_text(encoding="utf-8").strip(),
        )
        html = html.replace(
            "/* LEAF_MCP_SCRIPT */",
            bundle.read_text(encoding="utf-8")
            .strip()
            .replace("</script", "<\\/script"),
        )
        html = html.replace(
            "<!-- LEAF_MCP_ICON -->",
            (ASSETS / "icon.svg").read_text(encoding="utf-8").strip(),
        )
        out.write_text(html, encoding="utf-8")
        outputs.append(out)
    return outputs


BUILDS: dict[str, Callable[[Path], list[Path]]] = {
    "highlight": build_highlight,
    "mcp-app": build_mcp_app,
    "plot": build_plot,
    "pierre": build_pierre,
}


def vendor(name: str) -> list[Path]:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if name in COPIES:
            copy = COPIES[name]
            shutil.copyfile(unpack(copy.package, work) / copy.inside, copy.out)
            return [copy.out]
        return BUILDS[name](work)


# Which bundle a moved pin obliges you to rebuild. A copy answers for its own
# package; a build reaches for several, and esbuild is the tool all three share.
REBUILDS = {
    **{copy.package: (name,) for name, copy in COPIES.items()},
    "highlight.js": ("highlight",),
    "@observablehq/plot": ("plot",),
    "@pierre/diffs": ("pierre",),
    "@modelcontextprotocol/ext-apps": ("mcp-app",),
    "shiki": ("pierre",),
    "esbuild": ("highlight", "mcp-app", "plot", "pierre"),
}


def report_pins() -> None:
    """Every pin against upstream's latest, with the bundle to rebuild if it moved."""
    for package, pinned in PINS.items():
        latest = run(
            "npm", "view", f"{package}@latest", "version", cwd=ROOT, capture=True
        )
        rebuild = " ".join(REBUILDS[package])
        moved = "" if latest == pinned else f"latest {latest}"
        print(f"{package:22} {pinned:10} {rebuild:24} {moved}".rstrip())


def main() -> None:
    known = sorted(COPIES | BUILDS)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bundle", nargs="*", help=f"one or more of: {', '.join(known)}")
    parser.add_argument(
        "--pins",
        action="store_true",
        help="read every pin against upstream's latest, and name what to rebuild",
    )
    args = parser.parse_args()

    unknown = sorted(set(args.bundle) - set(known))
    if unknown:
        parser.error(f"unknown bundle: {', '.join(unknown)}")
    if args.pins:
        if args.bundle:
            parser.error("--pins reads every pin, so it takes no bundle")
        report_pins()
        return

    for name in args.bundle or known:
        for out in vendor(name):
            print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
