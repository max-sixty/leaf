/**
 * The third-party bundles Leaf ships outside the browser framework.
 *
 * Nothing builds them at install time, so they are tracked. The files under
 * `browser/vendor/` and each package's own `vendor/` are page payload:
 * `page init` copies them into a page directory and a user's browser runs them. A
 * vendored library is payload of the package whose widget draws with it, not of the
 * layer: Pele and Pierre reach a page only when it selects `diagram` or `diff`.
 *
 * Each row of `bundles` bundles only what its consumer needs, from the installed
 * packages and the registry's declarations; a directory under `build/entries/` named
 * after a row holds that row's inputs. A `.patch` beside this file starts with the
 * name of the row that applies it. Every version a bundle carries is the one
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
import { existsSync, readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatch, parsePatch } from "diff";
import { build } from "./esbuild.mjs";
import { bindToVendoredLit } from "./lit.mjs";
import { patchTransitions } from "./webawesome/transition-patch.mjs";
import { bundledPackages, checkModule, licenseNotices } from "./browser/shipped.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const assets = "browser";
const packageVendor = (name) => `packages/${name}/vendor`;
const input = (file) => path.join(root, "build", file);

/** The installed version of a package, which is the one the lock resolved. */
const version = (name) =>
  JSON.parse(
    readFileSync(path.join(root, "node_modules", name, "package.json"), "utf8"),
  ).version;

/** The registry's language names, the vocabulary `page check` accepts. */
const languageDeclarations = () =>
  JSON.parse(readFileSync(path.join(root, assets, "registry.json"), "utf8")).$languages;
const languages = () => languageDeclarations().names;

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

/** Bind side-effect-free libraries to the shared module a page serves at `target`. */
const bindTo = (filter, target) => ({
  name: `leaf-bind ${target}`,
  setup(builder) {
    builder.onResolve({ filter }, () => ({
      path: target,
      external: true,
      sideEffects: false,
    }));
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
  // Leaf captures without `reconcile` (`runtime/composing/page-image.js` says why), and
  // SnapDOM then warns on the console that text may wrap differently. The capture's own
  // `warnings` keep that notice; the console copy would read as a page problem.
  //
  // SnapDOM sends a resource's cookies when its origin is `location.origin`, which is
  // the URL's origin rather than the document's. In a live sample's sandboxed child the
  // document's origin is opaque, so every request is cross-origin and Leaf's server
  // answers it `Access-Control-Allow-Origin: *`, which a credentialed request may not
  // read: the child's own icon.svg mask failed with a CORS error in every capture.
  // Compare with the document's origin, `self.origin`, instead (SnapDOM 3.3.7).
  snapdom: () => ({
    out: `${assets}/vendor/snapdom.esm.js`,
    entryPoints: [input("entries/snapdom/entry.mjs")],
    adapt: [
      {
        file: /@zumer\/snapdom\/dist\/snapdom\.mjs$/,
        edit: (source) =>
          seam(
            seam(
              source,
              'y.origin===location.origin?"include":"omit"',
              'y.origin===self.origin?"include":"omit"',
              "SnapDOM credentials origin",
            ),
            'O.warnedReconcile||(O.warnedReconcile=!0,console.warn("[SnapDOM] Some text may wrap differently in the capture. Pass { reconcile: true } to fix it (about 2x slower)."))',
            "O.warnedReconcile=!0",
            "SnapDOM reconcile console warning",
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
    entryPoints: [input("entries/trace-images/entry.mjs")],
    mainFields: ["module", "main"],
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
    entryPoints: [input("entries/markdown/entry.mjs")],
    // Record block syntax where native rules consume it. Public maps expose only
    // lines; guessing delimiters again disagrees with containers and code content.
    // A list item also records the columns its later lines stand past its
    // container's, where the item's own blocks start.
    adapt: [
      {
        file: /markdown-it\/dist\/markdown-it\.mjs$/,
        edit: (source) =>
          [
            [
              "var StateBlock = class {",
              `function sourceSpan(state, line, from, to) {
                const start = state.src.lastIndexOf("\\n", from - 1) + 1;
                return [line, from - start, to - start];
              }
              var StateBlock = class {`,
            ],
            [
              'const token = state.push("fence", "code", 0);',
              `const token = state.push("fence", "code", 0);
          token.lfSource = { markers: [sourceSpan(state, startLine, state.bMarks[startLine] + state.tShift[startLine], state.eMarks[startLine])] };
          if (haveEndMarker) token.lfSource.markers.push(sourceSpan(state, nextLine, state.bMarks[nextLine] + state.tShift[nextLine], state.eMarks[nextLine]));`,
            ],
            [
              'token_o.markup = "########".slice(0, level);',
              `token_o.lfSource = { markers: [sourceSpan(state, startLine, state.bMarks[startLine] + state.tShift[startLine], state.skipSpaces(pos)), sourceSpan(state, startLine, max, state.eMarks[startLine])] };
          token_o.markup = "########".slice(0, level);`,
            ],
            [
              "token_o.markup = String.fromCharCode(marker);",
              `token_o.lfSource = { markers: [sourceSpan(state, nextLine, state.bMarks[nextLine] + state.tShift[nextLine], state.eMarks[nextLine])] };
          token_o.markup = String.fromCharCode(marker);`,
            ],
            ["const oldBMarks = [];", "const markers = []; const oldBMarks = [];"],
            [
              "oldBMarks.push(state.bMarks[nextLine]);\n\t\t\tstate.bMarks[nextLine] = pos;",
              "markers.push(sourceSpan(state, nextLine, state.bMarks[nextLine] + state.tShift[nextLine], pos));\n\t\t\toldBMarks.push(state.bMarks[nextLine]);\n\t\t\tstate.bMarks[nextLine] = pos;",
            ],
            [
              'token_o.markup = ">";',
              'token_o.lfSource = { markers }; token_o.markup = ">";',
            ],
            [
              'token = state.push("list_item_open", "li", 1);',
              `token = state.push("list_item_open", "li", 1);
          token.lfSource = { markers: [sourceSpan(state, nextLine, state.bMarks[nextLine] + state.tShift[nextLine], Math.min(posAfterMarker + 1, contentStart))], indent: indent - state.blkIndent };`,
            ],
          ].reduce(
            (text, [original, replacement]) =>
              seam(text, original, replacement, "Markdown block source"),
            source,
          ),
      },
    ],
  }),

  // Load the viewer with its own styles in one optional, exportable module.
  photoswipe: () => ({
    out: `${assets}/vendor/photoswipe.esm.js`,
    entryPoints: [input("entries/photoswipe/entry.mjs")],
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
    typeEntry: input("entries/sortable/entry.mjs"),
    finish: (source) =>
      'import {move as leafMove} from "/runtime/widget-api.js";\n' +
      /** @satisfies {[string, string, number?][]} */ ([
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
      ]).reduce(
        (text, [original, replacement, count]) =>
          seam(text, original, replacement, "Sortable clone", count),
        source,
      ),
  }),

  // Pele owns Mermaid parsing and rendering. Keep every diagram family in one
  // optional module, so offline exports share the browser's complete vocabulary
  // without fetching per-family chunks. The widget imports it only when it draws.
  pele: () => ({
    out: `${packageVendor("diagram")}/pele.esm.js`,
    entryPoints: [input("entries/pele/entry.mjs")],
    adapt: [
      {
        file: /pele\/dist\/pele\.js$/,
        // Pele consumes every HTML-looking label tag, discarding unsupported
        // tags such as a literal <img> code sample. Consume only the formatting
        // tags its tokenizer recognizes; other characters stay in its text buffer
        // and the SVG builder escapes them. Breaks are handled before this scan.
        edit: (source) =>
          seam(
            source,
            "if(b||o_.has(m)){c+=u[0].length;continue}",
            "if(b){c+=u[0].length;continue}",
            "Pele literal unsupported label tags",
          ),
      },
    ],
    platform: "browser",
    target: "chrome105",
    banner: {
      js: `/*! pele ${version("pele")} — MIT — licenses: pele.LICENSES.txt */`,
    },
  }),

  // One CodeMirror 6 core for runtime composers and optional file editors.
  //
  // One bundle holds the editor core and the GFM Markdown language, exporting the
  // names composers and the file-editor adapter import. Optional autocomplete and
  // merge live in the file-editor package and import this same state/view/language
  // implementation. The runtime owns the live-preview decorations and reads a draft
  // with markdown-it alone; only the file editor highlights with the language. It
  // comes without `markdown()`, whose HTML-block support would carry the HTML, CSS
  // and JavaScript grammars into the bundle for syntax a file never highlights.
  codemirror: () => ({
    out: `${assets}/vendor/codemirror.esm.js`,
    entryPoints: [input("entries/codemirror/entry.mjs")],
    banner: {
      js: `/*! CodeMirror ${version("@codemirror/view")} — MIT — https://codemirror.net */`,
    },
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
    entryPoints: [input("entries/file-editor/entry.mjs")],
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
    entryPoints: [input("entries/floating-ui/entry.mjs")],
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
  // loader map (`syntaxLoaders`) names each registry language's entry point.
  syntax: () => ({
    out: `${assets}/vendor/syntax.esm.js`,
    entryPoints: {
      "syntax.esm": input("entries/syntax/entry.mjs"),
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
    entryPoints: [input("entries/jsdiff/entry.mjs")],
    banner: {
      js: `/*! jsdiff ${version("diff")} — BSD-3-Clause — https://github.com/kpdecker/jsdiff */`,
    },
  }),

  blazediff: () => ({
    out: `${packageVendor("default")}/blazediff.js`,
    entryPoints: [input("entries/blazediff/entry.mjs")],
  }),

  // DBSCAN groups screenshot fragments by their original neighborhoods.
  "density-clustering": () => ({
    out: `${packageVendor("default")}/density-clustering.esm.js`,
    entryPoints: [input("entries/density-clustering/entry.mjs")],
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
    entryPoints: [input("entries/plot/entry.mjs")],
    banner: {
      js:
        `/*! @observablehq/plot ${version("@observablehq/plot")} — ISC — https://observablehq.com/plot\n` +
        ` *  bundled with d3 ${version("d3")} — ISC — https://d3js.org */`,
    },
  }),

  // Parsing is needed before a metadata row appears; static rendering waits for
  // textual evidence to open. Independent builds keep the shared public barrel
  // from hoisting the renderer into the parser's eager dependency graph.
  // Pierre's static renderer reads Leaf's syntax module for grammars, Shiki core
  // and the token theme. Its grammar and core imports are made static below so
  // offline exports can inline them without bundling Shiki's full catalogs.
  // The unused WASM import carries no binary or separate module.
  pierre: () => ({
    out: `${packageVendor("default")}/pierre-diffs.esm.js`,
    entryPoints: {
      "pierre-diffs.esm": input("entries/pierre/entry.mjs"),
      "pierre-parser.esm": input("entries/pierre/parser.mjs"),
    },
    outdir: packageVendor("default"),
    place: {
      [`${packageVendor("default")}/pierre-parser.esm.js`]: `${packageVendor("diff")}/pierre-parser.esm.js`,
    },
    adapt: [
      {
        file: /@pierre\/diffs\/dist\/highlighter\/backends\/shiki\.js$/,
        edit: (source) =>
          seam(
            source,
            'import("shiki/wasm")',
            "Promise.resolve({default: undefined})",
            "Pierre unused WASM import",
          ),
      },
      {
        file: /@pierre\/diffs\/dist\/highlighter\/languages\/resolveLanguage\.js$/,
        edit: (source) =>
          'import { bundledLanguages } from "shiki/langs";\n' +
          seam(
            source,
            'const { bundledLanguages } = await import("shiki/langs");',
            "",
            "Pierre shared grammar catalog",
          ),
      },
      {
        file: /@pierre\/diffs\/dist\/highlighter\/themes\/themeResolver\.js$/,
        edit: (source) =>
          'import * as leafShikiCore from "shiki/core";\n' +
          seam(
            source,
            'createCachedLoader(() => import("shiki/core"))',
            "createCachedLoader(() => Promise.resolve(leafShikiCore))",
            "Pierre shared Shiki core",
          ),
      },
    ],
    platform: "browser",
    external: ["/runtime/widget-api.js"],
    target: "chrome105",
    banner: {
      js: `/*! @pierre/diffs ${version("@pierre/diffs")} — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */`,
    },
    plugins: [
      bindTo(
        /^(?:shiki(?:\/(?:core|langs))?|\/vendor\/syntax\.esm\.js)$/,
        "./syntax.esm.js",
      ),
      {
        name: "leaf-pierre-shims",
        setup(builder) {
          builder.onResolve({ filter: /^@pierre\/theming\/themes$/ }, () => ({
            path: input("entries/pierre/themes-leaf.mjs"),
          }));
        },
      },
    ],
  }),

  // The optional file navigator uses Trees' vanilla model and its own shadow-DOM
  // renderer. Upstream includes its styles and Preact runtime; no React wrapper,
  // external stylesheet, or consumer build reaches the page.
  trees: () => ({
    out: `${packageVendor("file-tree")}/pierre-trees.esm.js`,
    entryPoints: [input("entries/trees/entry.mjs")],
    platform: "browser",
    target: "chrome105",
    // Keep upstream's core/override ordering inside the page's vendor tier, so
    // authored styles retain the same precedence as every other widget's.
    adapt: [
      {
        file: /@pierre\/trees\/dist\/model\/FileTreeController\.js$/,
        // beta.6 treats a nonempty query with no matches as unfiltered, exposing
        // unrelated root rows. The controller must retain an empty filtered set;
        // its existing empty-query branch remains the route back to all files.
        edit: (source) =>
          seam(
            seam(
              source,
              'this.#searchMode === "hide-non-matches" && matchingPaths.length > 0',
              'this.#searchMode === "hide-non-matches"',
              "Trees empty search-result set",
            ),
            'this.#searchMode !== "hide-non-matches" || this.#searchMatchPathSet.size === 0',
            'this.#searchMode !== "hide-non-matches"',
            "Trees empty search-result visibility",
          ),
      },
      {
        file: /@pierre\/trees\/dist\/utils\/cssWrappers\.js$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "return `${LAYER_ORDER}\n@layer base {\n  ${coreCSS}\n}`;",
              "return `@layer lf-base {\n${LAYER_ORDER}\n@layer base {\n  ${coreCSS}\n}\n}`;",
              "Trees core CSS cascade",
            ),
            "return `${LAYER_ORDER}\n@layer unsafe {\n  ${unsafeCSS}\n}`;",
            "return `@layer lf-base {\n${LAYER_ORDER}\n@layer unsafe {\n  ${unsafeCSS}\n}\n}`;",
            "Trees override CSS cascade",
          ),
      },
    ],
    banner: {
      js: `/*! @pierre/trees ${version("@pierre/trees")} — Apache-2.0 — licenses: pierre-trees.LICENSES.txt */`,
    },
  }),

  // Split chrome controls from optional widgets, sharing their dependency graph. Both
  // entry points register the same components once. Optional controls remain on
  // demand; the shared chunks are core payload because chrome also reads them. Lit
  // binds to the page's one copy (`build/lit.mjs`).
  webawesome: async () => ({
    out: `${packageVendor("default")}/webawesome.esm.js`,
    entryPoints: {
      "webawesome.esm": input("entries/webawesome/entry.mjs"),
      "webawesome-chrome": input("entries/webawesome/chrome.mjs"),
    },
    outdir: `${assets}/vendor`,
    place: {
      [`${assets}/vendor/webawesome.esm.js`]: `${packageVendor("default")}/webawesome.esm.js`,
    },
    splitting: true,
    chunkNames: "webawesome/[name]-[hash]",
    // Web Awesome 3.14.0 prepends a comment naming its docs to an element's shadow root
    // on every `connectedCallback`, so an element the chrome keeps and connects again,
    // as the floating panel's menu does its copy rows, grows by a node each time it
    // shows. The element module's adaptation, listed first so it wins its chunk, keeps
    // the one comment the first connection writes.
    adapt: [
      {
        file: /webawesome\/dist\/chunks\/chunk\.AOKMSJXD\.js$/,
        edit: (source) =>
          seam(
            source,
            "this.shadowRoot?.prepend(",
            "this.shadowRoot?.firstChild?.nodeType !== Node.COMMENT_NODE && this.shadowRoot?.prepend(",
            "Web Awesome docs comment",
            2,
          ),
      },
      {
        file: /webawesome\/dist\/chunks\/chunk\.ZAVDMBWV\.js$/,
        edit: patchTransitions,
      },
      // A radio group's arrow moves focus to the next radio in its row, which the user
      // already sees. Leaf places focus without scrolling (focus.js, `focusDestination`),
      // and the focused-control landing margin made the native scroll move the chooser
      // under the arrow wherever a landing had left it at the window's top edge.
      {
        file: /webawesome\/dist\/chunks\/chunk\.7YHRZ7G7\.js$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "radios[index].focus();",
              "radios[index].focus({ preventScroll: true });",
              "Web Awesome radio group arrow focus",
            ),
            'radios[index].shadowRoot.querySelector("button").focus();',
            'radios[index].shadowRoot.querySelector("button").focus({ preventScroll: true });',
            "Web Awesome radio button arrow focus",
          ),
      },
    ],
    platform: "browser",
    target: "chrome105",
    banner: {
      js: `/*! Web Awesome ${version("@awesome.me/webawesome")} — MIT — licenses: webawesome.LICENSES.txt */`,
    },
    plugins: [await bindToVendoredLit()],
  }),
};

/** One bundle's outputs, its license notices last, keyed by repository path. */
async function bundle(spec) {
  const {
    out,
    entry,
    copy,
    typeEntry: _typeEntry,
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

/**
 * The runtime's table of the grammars `syntax` bundles (`runtime/syntax-languages.js`):
 * a literal import for each, so an export binds it, and each name and alias Shiki
 * gives a grammar, which a native Markdown fence uses, read here so that identifying a
 * block loads no grammar. Both come from this build, which a page's grammars need
 * anyway, so the browser doesn't read `$languages.names` itself.
 */
async function syntaxLoaders() {
  const names = languages();
  const labels = {};
  for (const name of names) {
    const { default: grammars } = await import(`@shikijs/langs/${name}`);
    const grammar = grammars.find(
      (grammar) => grammar.name === name || grammar.aliases?.includes(name),
    );
    for (const label of [grammar.name, ...(grammar.aliases ?? [])])
      labels[label] = name;
  }
  return Buffer.from(
    "// Generated by build/vendor.mjs from registry.json's $languages.\n" +
      '/** @type {Record<string, () => Promise<{default: import("@shikijs/core").LanguageRegistration[]}>>} */\n' +
      "// prettier-ignore\nexport const syntaxLanguages = {\n" +
      names
        .map((name) => `  "${name}": () => import("/vendor/syntax/${name}.js"),\n`)
        .join("") +
      "};\n" +
      `/** @type {Record<string, string>} */\n// prettier-ignore\nexport const syntaxLanguageNames = ${JSON.stringify(labels)};\n` +
      `/** @type {Record<string, string>} */\n// prettier-ignore\nexport const syntaxLanguagePaths = ${JSON.stringify(languageDeclarations().paths)};\n`,
  );
}

/** Every bundle's outputs, and the runtime's syntax table, keyed by repository path. */
export async function vendorOutputs() {
  const built = await Promise.all(
    Object.values(bundles).map(async (spec) => bundle(await spec())),
  );
  return new Map([
    ...built.flatMap((outputs) => [...outputs]),
    [`${assets}/runtime/syntax-languages.js`, await syntaxLoaders()],
  ]);
}

/** Resolve a vendored public module to the entry that selects its native exports.
 * The checker follows the installed dependency's declarations through that entry. */
export async function vendorTypePaths() {
  const paths = {};
  for (const create of Object.values(bundles)) {
    const spec = await create();
    if ("typeEntry" in spec) {
      paths[`/vendor/${path.basename(spec.out)}`] = [spec.typeEntry];
      continue;
    }
    if (!("entryPoints" in spec)) continue;
    if (Array.isArray(spec.entryPoints)) {
      if (spec.entryPoints.length === 1)
        paths[`/vendor/${path.basename(spec.out)}`] = spec.entryPoints;
    } else {
      for (const [name, entry] of Object.entries(spec.entryPoints)) {
        if (path.isAbsolute(entry)) {
          paths[`/vendor/${name}.js`] = [entry];
          continue;
        }
        const resolved = fileURLToPath(import.meta.resolve(entry));
        // A bare entry can ship its declaration beside the exported JavaScript.
        // Keep that maintained contract instead of treating the dependency as JS.
        const declaration = resolved.replace(
          /\.(mjs|cjs|js)$/,
          (_, extension) => ({ mjs: ".d.mts", cjs: ".d.cts", js: ".d.ts" })[extension],
        );
        paths[`/vendor/${name}.js`] = [
          declaration !== resolved && existsSync(declaration) ? declaration : resolved,
        ];
      }
    }
  }
  return paths;
}
