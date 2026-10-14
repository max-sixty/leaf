/**
 * The third-party bundles Leaf ships outside the browser framework.
 *
 * Nothing builds them at install time, so they are tracked. The files under
 * `skills/leaf/assets/vendor/` and each package's own `vendor/` are page payload:
 * `page init` copies them into a page directory and a user's browser runs them. A
 * vendored library is payload of the package whose widget draws with it, not of the
 * layer: Mermaid and Pierre reach a page only when it selects `diagram` or `diff`.
 *
 * Each row of `bundles` bundles only what its consumer needs, from the installed
 * packages and the registry's declarations; a directory under `build/` named after a
 * row holds that row's inputs, and a `.patch` beside this file starts with the name of
 * the row that applies it. Every version a bundle carries is the one
 * `pnpm-lock.yaml` resolved: `package.json` names each package an entry imports, and
 * the lock settles the rest of the closure. An upstream module a bundle adapts is
 * edited as esbuild loads it, through `adapt`: a `seam` replaces text that must occur
 * exactly as often as stated, and a `.patch` beside this file applies a recorded
 * upstream backport. A changed seam, a patch that no longer applies, or an adaptation
 * whose module the bundle no longer loads fails the build, so an upgrade rechecks
 * each one. `node_modules` is never written.
 *
 * Every output passes through `build/browser/shipped.mjs`: it refuses a module an
 * export cannot load, and each bundle's `<name>.LICENSES.txt` states the packages that
 * reached it. `build/browser/build.mjs` writes and checks these outputs with its own.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatch, parsePatch } from "diff";
import { build } from "esbuild";
import { parse } from "acorn";
import { bindToVendoredLit } from "./lit.mjs";
import { patchTransitions } from "./webawesome/transition-patch.mjs";
import { bundledPackages, checkModule, licenseNotices } from "./browser/shipped.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const assets = "skills/leaf/assets";
const packageVendor = (name) => `skills/leaf/packages/${name}/vendor`;
const input = (file) => path.join(root, "build", file);

/** Expose selected installed exports without sharing a broad barrel's unused imports. */
function selectedExports(source, entry) {
  const options = { ecmaVersion: "latest", sourceType: "module" };
  const names = parse(readFileSync(entry, "utf8"), options).body.flatMap((node) =>
    node.specifiers.map((item) => item.local.name),
  );
  const body = parse(source, options).body;
  const published = body
    .filter((node) => node.type === "ExportNamedDeclaration")
    .flatMap((node) => node.specifiers.map((item) => item.exported.name));
  if (!names.every((name) => published.includes(name)))
    throw new Error("Pierre public export seam changed");
  const imports = body
    .filter((node) => node.type === "ImportDeclaration")
    .flatMap((node) =>
      node.specifiers
        .filter((item) => names.includes(item.local.name))
        .map(
          (item) =>
            `export { ${item.imported.name} } from ${JSON.stringify(node.source.value)};`,
        ),
    );
  if (imports.length !== names.length) throw new Error("Pierre export seam changed");
  return imports.join("\n");
}

/** The installed version of a package, which is the one the lock resolved. */
const version = (name) =>
  JSON.parse(readFileSync(path.join(root, "node_modules", name, "package.json")))
    .version;

/** The registry's language names, the vocabulary `page check` accepts. */
const languages = () =>
  JSON.parse(readFileSync(path.join(root, assets, "registry.json"))).$languages.names;

/** Replace text an upstream module must contain exactly `count` times. */
export function seam(source, original, replacement, what, count = 1) {
  if (source.split(original).length - 1 !== count)
    throw new Error(`${what} seam changed: ${original}`);
  return source.replaceAll(original, replacement);
}

/** Apply recorded patches to the modules they name, in order. */
function patches(...files) {
  const recorded = files.flatMap((file) =>
    parsePatch(readFileSync(input(file), "utf8")).map((patch) => ({
      file,
      patch,
      module: patch.newFileName.slice(patch.newFileName.indexOf("node_modules/")),
    })),
  );
  const escape = (text) => text.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
  return {
    file: new RegExp(`(?:${recorded.map(({ module }) => escape(module)).join("|")})$`),
    edit: (source, at) =>
      recorded
        .filter(({ module }) => at.endsWith(module))
        .reduce((text, { file, patch }) => {
          const patched = applyPatch(text, patch);
          if (patched === false) throw new Error(`${file} no longer applies to ${at}`);
          return patched;
        }, source),
  };
}

/**
 * An esbuild plugin editing upstream modules as they load. Each adaptation names
 * the modules it edits by path, one adaptation to a module; one that edits nothing in
 * a build fails it.
 */
export function adapt(adaptations) {
  const used = new Set();
  return {
    name: "leaf-adapt",
    setup(builder) {
      adaptations.forEach(({ file, edit }, index) =>
        builder.onLoad({ filter: file }, async ({ path: at }) => {
          used.add(index);
          return {
            contents: await edit(await readFile(at, "utf8"), at),
            resolveDir: path.dirname(at),
          };
        }),
      );
      builder.onEnd((result) => {
        if (result.errors.length) return;
        for (const [index, { file }] of adaptations.entries())
          if (!used.has(index)) throw new Error(`no module matches adaptation ${file}`);
      });
    },
  };
}

/** Resolve the specifiers `filter` matches to one module a page serves at `target`. */
const bindTo = (filter, target) => ({
  name: `leaf-bind ${target}`,
  setup(builder) {
    builder.onResolve({ filter }, () => ({ path: target, external: true }));
  },
});

/**
 * Each bundle, by name. A row's `out` is its first output, which names the bundle's
 * license notices. Rows give esbuild either `entry`, a module's source, or their own
 * entry points, and may add `adapt`ations, esbuild options, and a `place` for an
 * output committed outside the build's directory. A `copy` row takes a published
 * file as it stands instead, and may `finish` it.
 */
const bundles = {
  // Browser-native DOM rasterization, loaded only when capturing a page region.
  //
  // After a capture, SnapDOM counts each later mutation against the target's
  // ancestors, climbing out of a shadow tree through `getRootNode().host`. A target
  // removed with its subtree has that subtree's top element as its root, and an `<a>`
  // there answers `host` with its URL's host string. SnapDOM 3.3.0 to 3.3.3 then use
  // that string as a WeakMap key, so a removed link throws from the observer, an
  // uncaught page error. Climb only from an element whose parent is a shadow root.
  snapdom: () => ({
    out: `${assets}/vendor/snapdom.esm.js`,
    entry: 'export { snapdom } from "@zumer/snapdom";\n',
    adapt: [
      {
        file: /@zumer\/snapdom\/dist\/snapdom\.mjs$/,
        edit: (source) =>
          seam(
            source,
            "for(;r;r=r.parentElement||r.getRootNode?.()?.host)",
            "for(;r;r=r.parentElement||(r.parentNode?.nodeType===11?r.parentNode.host:null))",
            "SnapDOM mutation-ancestor",
          ),
      },
    ],
  }),

  // Framework-free image inspection, loaded only by the Playwright widget. Scoped CSS
  // travels with the module so offline exports use the same library rendering as
  // served pages.
  //
  // Viewer schedules a class write 300 ms after an inline image is viewed even with
  // transitions disabled. It changes no paint, but wakes Leaf's margin layout after
  // presentation, so the write is scheduled only when transitions are on.
  "trace-images": () => ({
    out: `${packageVendor("playwright")}/images.esm.js`,
    entry:
      'export { default as Viewer } from "viewerjs/dist/viewer.esm.js";\n' +
      'export { default as css } from "viewerjs/dist/viewer.css";\n',
    loader: { ".css": "text" },
    adapt: [
      {
        file: /viewerjs\/dist\/viewer\.esm\.js$/,
        edit: (source) =>
          seam(
            source,
            `        setTimeout(function () {
          toggleClass(image, CLASS_TRANSITION, options.transition);
        }, 300);`,
            `        if (options.transition) {
          setTimeout(function () {
            toggleClass(image, CLASS_TRANSITION, options.transition);
          }, 300);
        }`,
            "Viewer post-view transition",
          ),
      },
    ],
  }),

  // One lazy Markdown parser bundle, including its task-list extension.
  markdown: () => ({
    out: `${assets}/vendor/markdown-it.esm.js`,
    entry:
      'export { default as MarkdownIt } from "markdown-it";\n' +
      'export { default as taskLists } from "markdown-it-task-lists";\n',
  }),

  // Load the viewer with its own styles in one optional, exportable module.
  photoswipe: () => ({
    out: `${assets}/vendor/photoswipe.esm.js`,
    entry:
      'export { default } from "photoswipe";\n' +
      'export { default as styles } from "photoswipe/style.css";\n',
    loader: { ".css": "text" },
    banner: { js: `/*! PhotoSwipe ${version("photoswipe")} — MIT — photoswipe.com */` },
  }),

  // Prepare clones before insertion and preserve the existing card's native state.
  //
  // Sortable's clone/start hooks run after creation/insertion, too late to stop a
  // checked radio joining the source's group or a nested widget activating. The
  // optional cloneElement factory prepares compact native motion previews at both
  // creation sites. Existing dragEl relocations use the shared move primitive,
  // preserving native state where supported and reordering by insertion elsewhere; as
  // package payload, the bundle takes it from the public widget-api.js.
  // Keep the upstream ESM/autoscroll implementation otherwise intact: the module
  // entry mounts autoscroll, unlike core; complete adds unused swap and multi-drag.
  sortable: () => ({
    out: `${packageVendor("default")}/sortable.esm.js`,
    copy: "sortablejs/modular/sortable.esm.js",
    finish: (source) =>
      'import {move as leafMove} from "/runtime/widget-api.js";\n' +
      [
        [
          "ghostEl = dragEl.cloneNode(true);",
          "ghostEl = options.cloneElement ? options.cloneElement(dragEl) : dragEl.cloneNode(true);",
        ],
        [
          "cloneEl = clone(dragEl);",
          "cloneEl = this.options.cloneElement ? this.options.cloneElement(dragEl) : clone(dragEl);",
        ],
        ["rootEl.insertBefore(dragEl, nextEl);", "leafMove(rootEl, dragEl, nextEl);"],
        ["rootEl.appendChild(dragEl);", "leafMove(rootEl, dragEl, null);"],
        [
          "el.insertBefore(dragEl, elLastChild.nextSibling);",
          "leafMove(el, dragEl, elLastChild.nextSibling);",
        ],
        ["el.insertBefore(dragEl, firstChild);", "leafMove(el, dragEl, firstChild);"],
        [
          "target.parentNode.insertBefore(dragEl, after ? nextSibling : target);",
          "leafMove(target.parentNode, dragEl, after ? nextSibling : target);",
        ],
        [
          "this.sortable.el.insertBefore(dragEl, nextSibling);",
          "leafMove(this.sortable.el, dragEl, nextSibling);",
        ],
        [
          "this.sortable.el.appendChild(dragEl);",
          "leafMove(this.sortable.el, dragEl, null);",
        ],
        // Both remaining appends, once the sortable's own has been replaced above.
        ["el.appendChild(dragEl);", "leafMove(el, dragEl, null);", 2],
      ].reduce(
        (text, [original, replacement, count]) =>
          seam(text, original, replacement, "Sortable clone", count),
        source,
      ),
  }),

  // Bundle the canonical Mermaid parser and renderers for offline use. Upstream loads
  // its diagram families with dynamic imports; statically including them keeps the
  // bundle self-contained in an export, and the widget still imports this optional
  // package only when it draws a diagram.
  mermaid: () => ({
    out: `${packageVendor("diagram")}/mermaid.esm.js`,
    entry: 'export { default } from "mermaid";\n',
    platform: "browser",
    target: "chrome105",
    supported: { "dynamic-import": false },
    banner: {
      js: `/*! mermaid ${version("mermaid")} — MIT — licenses: mermaid.LICENSES.txt */`,
    },
  }),

  // One CodeMirror 6 core for runtime composers and optional file editors.
  //
  // One bundle holds the editor core and the GFM Markdown language, exporting the
  // names composers and the file-editor adapter import. Optional autocomplete and
  // merge live in the file-editor package and import this same state/view/language
  // implementation. The runtime owns the live-preview decorations; nothing here
  // styles a document. The language comes without `markdown()`, whose HTML-block
  // support would carry the HTML, CSS and JavaScript grammars into the bundle for
  // syntax a comment never highlights.
  codemirror: () => ({
    out: `${assets}/vendor/codemirror.esm.js`,
    entry:
      `/*! CodeMirror ${version("@codemirror/view")} — MIT — https://codemirror.net */\n` +
      'export { EditorView, keymap, Decoration, ViewPlugin } from "@codemirror/view";\n' +
      'export { EditorState, StateEffect, Compartment } from "@codemirror/state";\n' +
      "export { history, standardKeymap, historyKeymap, isolateHistory, invertedEffects }" +
      ' from "@codemirror/commands";\n' +
      'export { LanguageSupport } from "@codemirror/language";\n' +
      "export { markdownLanguage, insertNewlineContinueMarkup }" +
      ' from "@codemirror/lang-markdown";\n' +
      'export { ChangeSet, EditorSelection, Prec, Transaction, Annotation, Facet, RangeSet, RangeSetBuilder, StateField, Text, codePointAt, codePointSize, fromCodePoint, combineConfig, MapMode, RangeValue, CharCategory } from "@codemirror/state";\n' +
      'export { drawSelection, lineNumbers, highlightActiveLineGutter, highlightActiveLine, dropCursor, rectangularSelection, crosshairCursor, GutterMarker, gutter, WidgetType, logException, Direction, showTooltip, getTooltip, placeholder } from "@codemirror/view";\n' +
      'export { defaultKeymap } from "@codemirror/commands";\n' +
      'export { HighlightStyle, syntaxHighlighting, indentOnInput, bracketMatching, syntaxTree, indentUnit, language, highlightingFor } from "@codemirror/language";\n' +
      'export { tags, highlightTree } from "@lezer/highlight";\n',
    adapt: [
      // The view's wrapping estimates must refresh when the content width changes.
      // CodeMirror 6.43.13 overwrites its previous width before comparing the two,
      // leaving the height oracle at the old measure. An expanding composer can then
      // exhaust the measurement loop as each newly rendered line corrects that guess.
      // Compare against the oracle's measured line length, with its five-column
      // floor, so sub-character resizes accumulate until they warrant a measurement.
      {
        file: /@codemirror\/view\/dist\/index\.js$/,
        edit: (source) =>
          seam(
            source,
            "Math.abs(contentWidth - this.contentDOMWidth) > oracle.charWidth",
            "Math.abs(Math.max(5, contentWidth / oracle.charWidth) - oracle.lineLength) > 1",
            "CodeMirror wrapping measurement",
          ),
      },
      // CodeMirror's style-mod provider expands its selectors and mounts its sheets,
      // and has no cascade-layer option. Wrap each module's rules once generated, so
      // base themes and syntax highlights share Leaf's `lf-base` tier and page CSS
      // takes part in the ordinary cascade. Wrapping the input spec instead would
      // expand CodeMirror's &light/&dark selectors against the at-rule rather than
      // their editor class.
      {
        file: /style-mod\/src\/style-mod\.js$/,
        edit: (source) => {
          const generation =
            "for (let prop in spec) render(splitSelector(prop), spec[prop], this.rules)";
          return seam(
            source,
            generation,
            generation +
              '\n    this.rules = ["@layer lf-base {\\n" + this.getRules() + "\\n}"]',
            "CodeMirror style-module generation",
          );
        },
      },
    ],
  }),

  // File editing extensions sharing the runtime's CodeMirror implementation. Merge
  // and autocomplete live in this optional package; their state/view/language
  // imports bind to the core Leaf's composers use, so extensions never mix
  // CodeMirror identities.
  "file-editor": () => ({
    out: `${packageVendor("file-editor")}/extensions.esm.js`,
    entry:
      'export { diff, unifiedMergeView, getOriginalDoc, originalDocChangeEffect } from "@codemirror/merge";\n' +
      'export { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";',
    platform: "browser",
    target: "es2022",
    plugins: [
      bindTo(
        /^(?:@codemirror\/(?:state|view|language)|@lezer\/highlight)$/,
        "/vendor/codemirror.esm.js",
      ),
    ],
  }),

  // The browser's anchored-positioning primitive. Floating UI's DOM package leaves
  // its core and utility packages as bare imports, which a page cannot resolve, so the
  // three become one module exporting only the middleware Leaf's floating chrome uses.
  //
  // `floating-ui-zoom.patch` backports upstream CSS-zoom support, merged but absent
  // from published 1.8.0 (floating-ui/floating-ui#3492, commit
  // 584a3afb1174ec00a371624afde50fc052b75a32). `floating-ui-element-zoom.patch`
  // locally completes the same platform conversion, kept apart from the verbatim
  // backport: relative CSS zoom scales positioning pixels, and parent borders cross
  // into viewport pixels with its scale.
  "floating-ui": () => ({
    out: `${assets}/vendor/floating-ui.esm.js`,
    entry:
      "export { autoUpdate, getOverflowAncestors, computePosition, flip, limitShift, offset, shift, size } " +
      'from "@floating-ui/dom";\n',
    platform: "browser",
    target: "chrome105",
    banner: {
      js:
        `/*! @floating-ui/dom ${version("@floating-ui/dom")} — MIT` +
        " — licenses: floating-ui.LICENSES.txt */",
    },
    adapt: [patches("floating-ui-zoom.patch", "floating-ui-element-zoom.patch")],
  }),

  // Share one Shiki engine between code blocks and Pierre, loading grammars only for
  // languages the page draws. Static imports share embedded grammars; the runtime's
  // loader map (`build/registry.mjs`) names each registry language's entry point.
  syntax: () => ({
    out: `${assets}/vendor/syntax.esm.js`,
    entryPoints: {
      "syntax.esm": input("syntax/entry.mjs"),
      ...Object.fromEntries(
        languages().map((name) => [`syntax/${name}`, `@shikijs/langs/${name}`]),
      ),
    },
    outdir: `${assets}/vendor`,
    chunkNames: "syntax/chunk-[hash]",
    splitting: true,
    platform: "browser",
    target: "chrome105",
  }),

  // Bundle only jsdiff's array comparison for the core browser runtime.
  jsdiff: () => ({
    out: `${assets}/vendor/jsdiff.esm.js`,
    entry:
      `/*! jsdiff ${version("diff")} — BSD-3-Clause — https://github.com/kpdecker/jsdiff */\n` +
      'export { diffArrays } from "diff/lib/diff/array.js";\n',
  }),

  // DBSCAN groups screenshot fragments by their original neighborhoods.
  "density-clustering": () => ({
    out: `${assets}/vendor/density-clustering.esm.js`,
    entry: 'export { default as DBSCAN } from "density-clustering/lib/DBSCAN.js";\n',
  }),

  // The optional DOM renderer loaded when a composer first carries a drawing.
  //
  // Every source needs computed styles and the requested crop. Upstream skips both
  // for resource-free SVG roots, returning the live SVG before any clone hook runs;
  // removing that shortcut sends SVG down the dependency's ordinary foreignObject
  // path. A sample's opaque origin cannot read the nested scratch iframe; the
  // dependency already uses an empty default-style map when no iframe exists, and
  // copying all computed properties is the same safe fallback there.
  "drawing-context": () => ({
    out: `${assets}/vendor/drawing-context.esm.js`,
    entry: 'export { domToCanvas } from "modern-screenshot";',
    adapt: [
      {
        file: /modern-screenshot\/dist\/index\.mjs$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "  if (isElementNode(context.node) && isSVGElementNode(context.node) && !svgHasExternalResources(context.node))\n    return context.node;\n",
              "",
              "modern-screenshot's SVG shortcut",
            ),
            "  const sandboxDocument = sandboxWindow?.document;\n",
            `  let sandboxDocument;
  try {
    sandboxDocument = sandboxWindow?.document;
  } catch (error) {
    if (error?.name !== "SecurityError") throw error;
    // A sample's opaque origin cannot read the nested scratch iframe. The
    // dependency already uses an empty default-style map when no iframe exists;
    // copying all computed properties is the same safe fallback here.
    const styles = new Map();
    defaultComputedStyles.set(key, styles);
    return styles;
  }
`,
            "modern-screenshot's scratch iframe",
          ),
      },
    ],
  }),

  // Observable Plot, which lf-chart hands a page's author. Nothing published is
  // loadable as it stands: `src/index.js` imports d3 by bare specifier,
  // `dist/plot.umd.min.js` reads a `d3` global the page would have to load first, and
  // a CDN's prebuilt ESM (jsdelivr's `+esm`) is smaller only because it imports d3
  // from a second URL, while the layer loads nothing from the network so a chart
  // draws offline and in an export. So this is Plot and the parts of d3 it reaches
  // for, in one module with no specifier left in it; vendoring d3 whole beside it
  // would be 100KB more and two files whose versions can drift apart. The whole of
  // Plot goes in, since an author writes the chart in Plot's own API.
  plot: () => ({
    out: `${packageVendor("default")}/plot.esm.js`,
    entry: 'export * from "@observablehq/plot";\n',
    banner: {
      js:
        `/*! @observablehq/plot ${version("@observablehq/plot")} — ISC — https://observablehq.com/plot\n` +
        ` *  bundled with d3 ${version("d3")} — ISC — https://d3js.org */`,
    },
  }),

  // Parsing is needed before a metadata row appears; static rendering waits for
  // textual evidence to open. One graph shares their common implementation.
  // Pierre's static renderer uses the shared Leaf syntax engine: Shiki binds to
  // `syntax.esm.js`, and Pierre's theme registry binds to Leaf's theme shim.
  // The unused WASM import carries no binary or separate module.
  pierre: () => ({
    out: `${packageVendor("diff")}/pierre-diffs.esm.js`,
    entryPoints: {
      "pierre-diffs.esm": input("pierre/entry.mjs"),
      "pierre-parser.esm": input("pierre/parser.mjs"),
    },
    outdir: packageVendor("diff"),
    splitting: true,
    chunkNames: "pierre/[name]-[hash]",
    adapt: [
      {
        file: /@pierre\/diffs\/dist\/index\.js$/,
        edit: (source) => selectedExports(source, input("pierre/parser.mjs")),
      },
      {
        file: /@pierre\/diffs\/dist\/ssr\/index\.js$/,
        edit: (source) => selectedExports(source, input("pierre/entry.mjs")),
      },
      {
        file: /@pierre\/diffs\/dist\/highlighter\/shared_highlighter\.js$/,
        edit: (source) =>
          seam(
            source,
            'import("shiki/wasm")',
            "Promise.resolve({default: undefined})",
            "Pierre unused WASM import",
          ),
      },
    ],
    platform: "browser",
    target: "chrome105",
    banner: {
      js: `/*! @pierre/diffs ${version("@pierre/diffs")} — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */`,
    },
    plugins: [
      bindTo(/^shiki$/, "./syntax.esm.js"),
      {
        name: "leaf-pierre-shims",
        setup(builder) {
          builder.onResolve({ filter: /^@pierre\/theming\/themes$/ }, () => ({
            path: input("pierre/themes-leaf.mjs"),
          }));
        },
      },
    ],
  }),

  // Split chrome controls from optional widgets, sharing their dependency graph. Both
  // entry points register the same components once. Optional controls remain on
  // demand; the shared chunks are core payload because chrome also reads them. Lit
  // binds to the page's one copy (`build/lit.mjs`).
  webawesome: async () => ({
    out: `${packageVendor("default")}/webawesome.esm.js`,
    entryPoints: {
      "webawesome.esm": input("webawesome/entry.mjs"),
      "webawesome-chrome": input("webawesome/chrome.mjs"),
    },
    outdir: `${assets}/vendor`,
    place: {
      [`${assets}/vendor/webawesome.esm.js`]: `${packageVendor("default")}/webawesome.esm.js`,
    },
    splitting: true,
    chunkNames: "webawesome/[name]-[hash]",
    external: ["/runtime/shadow-stage.js"],
    adapt: [{ file: /webawesome\/dist\/chunks\/.*\.js$/, edit: patchTransitions }],
    platform: "browser",
    target: "chrome105",
    banner: {
      js: `/*! Web Awesome ${version("@awesome.me/webawesome")} — MIT — licenses: webawesome.LICENSES.txt */`,
    },
    plugins: [
      await bindToVendoredLit(),
      {
        name: "leaf-wa-theme",
        setup(builder) {
          builder.onResolve({ filter: /^\.\/theme\.mjs$/ }, () => ({
            path: "theme.mjs",
            namespace: "leaf-wa-theme",
          }));
          builder.onLoad({ filter: /.*/, namespace: "leaf-wa-theme" }, async () => ({
            contents: `import { registerWidgetStyles } from "/runtime/shadow-stage.js";
registerWidgetStyles("Web Awesome", ${JSON.stringify(await webawesomeTheme())});`,
          }));
        },
      },
      {
        name: "leaf-wa-transitions",
        setup(builder) {
          builder.onResolve({ filter: /^leaf-wa-transitions$/ }, () => ({
            path: input("webawesome/transitions.mjs"),
          }));
        },
      },
    ],
  }),
};

/**
 * Web Awesome's theme, scoped to the controls Leaf bundles.
 *
 * Only upstream theme variables move to component hosts: transplanting root
 * appearance would override component state ink, and `leaf-theme.css` owns the chosen
 * typography defaults. The selectors also work in Leaf's declared shadow stages.
 * `webawesome/theme.py` selects the variables with the CSS parser Leaf's runtime
 * already depends on.
 */
async function webawesomeTheme() {
  const css = await build({
    entryPoints: [
      fileURLToPath(
        import.meta.resolve("@awesome.me/webawesome/dist/styles/themes/default.css"),
      ),
    ],
    bundle: true,
    minify: true,
    write: false,
  });
  const tokens = execFileSync(
    "uv",
    ["run", "--quiet", "python", input("webawesome/theme.py")],
    { cwd: root, input: css.outputFiles[0].text, encoding: "utf8" },
  );
  const hosts =
    "wa-copy-button, wa-comparison, wa-radio-group, wa-radio, wa-slider, wa-tooltip, wa-select, wa-option, wa-input";
  const leafTheme = await readFile(input("webawesome/leaf-theme.css"), "utf8");
  return `/* Generated by build/vendor.mjs webawesome. Web Awesome ${version("@awesome.me/webawesome")} — MIT; see vendor/webawesome.LICENSES.txt */\n@layer lf-vendor{@scope (:is(${hosts})){${tokens}}\n${leafTheme}}`;
}

/** One bundle's outputs, its license notices last, keyed by repository path. */
async function bundle(spec) {
  const {
    out,
    entry,
    copy,
    finish = (source) => source,
    adapt: adaptations = [],
    place = {},
    plugins = [],
    ...options
  } = spec;
  const outputs = new Map();
  let packages;
  if (copy) {
    const name = copy
      .split("/")
      .slice(0, copy.startsWith("@") ? 2 : 1)
      .join("/");
    outputs.set(
      out,
      Buffer.from(
        finish(await readFile(path.join(root, "node_modules", copy), "utf8")),
      ),
    );
    packages = [path.join(root, "node_modules", name)];
  } else {
    const result = await build({
      absWorkingDir: root,
      ...(entry === undefined
        ? {}
        : { stdin: { contents: entry, resolveDir: root, sourcefile: "entry.mjs" } }),
      ...(options.outdir ? {} : { outfile: out }),
      plugins: [...plugins, ...(adaptations.length ? [adapt(adaptations)] : [])],
      bundle: true,
      format: "esm",
      minify: true,
      legalComments: "inline",
      metafile: true,
      write: false,
      logLevel: "warning",
      ...options,
    });
    for (const file of result.outputFiles) {
      const name = path.relative(root, file.path).split(path.sep).join("/");
      outputs.set(place[name] ?? name, Buffer.from(file.contents));
    }
    packages = bundledPackages(result.metafile, root);
  }
  for (const [name, bytes] of outputs)
    if (name.endsWith(".js")) checkModule(bytes.toString(), name);
  const notices = `${path.posix.dirname(out)}/${path.posix.basename(out).split(".")[0]}.LICENSES.txt`;
  outputs.set(
    notices,
    Buffer.from(
      licenseNotices(path.posix.basename(notices, ".LICENSES.txt"), packages),
    ),
  );
  return outputs;
}

/** Every bundle's outputs, keyed by repository path. */
export async function vendorOutputs() {
  const built = await Promise.all(
    Object.values(bundles).map(async (spec) => bundle(await spec())),
  );
  return new Map(built.flatMap((outputs) => [...outputs]));
}
