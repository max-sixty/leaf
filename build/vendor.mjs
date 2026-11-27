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
 * a build fails it. An edited module loads as the build's `loader` option says for its
 * extension, as a stylesheet bundled as text does.
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
            // esbuild reads what a plugin returns as JavaScript unless told otherwise.
            loader: builder.initialOptions.loader?.[path.extname(at)],
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
 * output committed outside the build's directory, and name in `inlined` the packages
 * a prebuilt input carries inside it, which no input names (`bundledPackages`). A
 * `copy` row takes a published file as it stands instead, and may `finish` it.
 */
const bundles = {
  // Browser-native DOM rasterization, loaded only when capturing a page region.
  snapdom: () => ({
    out: `${assets}/vendor/snapdom.esm.js`,
    entryPoints: [input("entries/snapdom/entry.mjs")],
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

  // Effect and Effect UI, the component model a widget ported from Lit draws with
  // (runtime/effect-widget.js; browser/AGENTS.md, "Renderers"). One module, so a page
  // runs one Effect runtime.
  // The `production` condition picks Effect UI's builds without its development
  // checks and hot reload, which read session storage and scan every root at each
  // mount.
  "effect-ui": () => ({
    out: `${assets}/vendor/effect-ui.js`,
    entryPoints: [input("entries/effect-ui/entry.mjs")],
    conditions: ["production"],
    banner: {
      js: `/*! effect ${version("effect")} and @effect/ui ${version("@effect/ui")} — MIT — https://github.com/Effect-TS/ui */`,
    },
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
        edit: (source) =>
          [
            // Pele consumes every HTML-looking label tag, discarding unsupported
            // tags such as a literal <img> code sample. Consume only the formatting
            // tags its tokenizer recognizes; other characters stay in its text buffer
            // and the SVG builder escapes them. Breaks are handled before this scan.
            [
              "if(y||aT.has(m)){c+=d[0].length;continue}",
              "if(y){c+=d[0].length;continue}",
              "Pele literal unsupported label tags",
            ],
            // Pele measures labels on an OffscreenCanvas where one exists. Firefox's
            // resolves `system-ui`, Leaf's sans, to another face than the page draws
            // in, so at 12px "admits it, reads the whole log" measured 144px where the
            // page draws it 166px, and labels ran past their boxes. A canvas the
            // document makes measures in the page's own fonts, in every engine.
            [
              'if(e.OffscreenCanvas)return new e.OffscreenCanvas(1,1).getContext("2d");if(e.document)return e.document.createElement("canvas").getContext("2d")',
              'if(e.document)return e.document.createElement("canvas").getContext("2d");if(e.OffscreenCanvas)return new e.OffscreenCanvas(1,1).getContext("2d")',
              "Pele text measurer",
            ],
            // Pele's flowchart renderers write an edge's classes on its group, but
            // its converters replace the authored classes with fixed ones, and an
            // edge label's group takes none. Carry the authored classes to both, as
            // a node's reach its group, so page CSS can mark an edge in theme tokens.
            [
              'minlen:b.length,classes:"edge-thickness-normal edge-pattern-solid flowchart-link",arrowTypeStart:"none"',
              'minlen:b.length,classes:"edge-thickness-normal edge-pattern-solid flowchart-link "+b.classes.join(" "),arrowTypeStart:"none"',
              "Pele edge classes",
            ],
            [
              'classes:x.stroke==="invisible"?"":"edge-thickness-normal edge-pattern-solid flowchart-link",',
              'classes:(x.stroke==="invisible"?"":"edge-thickness-normal edge-pattern-solid flowchart-link ")+x.classes.join(" "),',
              "Pele edge classes",
            ],
            [
              'function ln(e,t,n,r,i,s){let a=t.width+8,o=t.height;return`<g class="pele-edge-label" data-id',
              'function ln(e,t,n,r,i,s,cl=""){let a=t.width+8,o=t.height;return`<g class="pele-edge-label${cl}" data-id',
              "Pele edge label classes",
            ],
            [
              'ln(ne.id,q,J,te,se?.text??"",h)',
              'ln(ne.id,q,J,te,se?.text??"",h,ue)',
              "Pele edge label classes",
            ],
            [
              'ln(ne.id,q,J,te,k?.text??"",y)',
              'ln(ne.id,q,J,te,k?.text??"",y,Nt(ne.classes.replace(/edge-thickness-normal|edge-pattern-solid|flowchart-link/g,"")))',
              "Pele edge label classes",
            ],
          ].reduce((text, edit) => seam(text, ...edit), source),
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
  // One bundle holds the editor core, exporting the names composers and the
  // file-editor adapter import. Optional autocomplete and merge live in the
  // file-editor package and import this same state/view/language implementation.
  // The runtime owns the live-preview decorations and reads a draft with markdown-it
  // alone, and the file editor colours every language with the syntax module, so the
  // core carries no language of its own.
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
      //
      // CodeMirror scroll walk: the view finds the boxes that scroll an editor by
      // walking up from it until `body`, and takes the window where it finds none. A
      // drag selection scrolls the nearest one on each axis while the pointer stands
      // past its edge, and the view's measure keeps the nearest vertical one at its
      // end, if it stood there, as the editor changes height. No scroll outside a box
      // fixed to the window moves the words inside it, so the walk ends at such a box
      // and takes it for each axis it found no scroller on. That box doesn't scroll, so
      // the page stays still under every editor in Leaf's chrome, each of which stands
      // in one. A fixed box whose containing block is an ancestor, as a transform or
      // paint containment makes one, has that ancestor for its `offsetParent` and
      // moves with that ancestor's scrollers, so the walk passes it. Walking on from
      // the chrome, which stands after `body` (runtime/base/chrome.js), the walk would reach
      // the root, whose own box moves up as the page scrolls: a press whose pointer
      // drifted a pixel would read the pointer as far below that box and scroll the
      // page to its end. Ending the walk at the root would give these editors the
      // window, which a drag at the window's foot would scroll, and which the measure
      // would scroll by the height a draft gives up at the page's end.
      // CodeMirror 6.43.15.
      {
        file: /@codemirror\/view\/dist\/index\.js$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "Math.abs(contentWidth - this.contentDOMWidth) > oracle.charWidth",
              "Math.abs(Math.max(5, contentWidth / oracle.charWidth) - oracle.lineLength) > 1",
              "CodeMirror wrapping measurement",
            ),
            "                x = cur;\n            cur = cur.assignedSlot || cur.parentNode;",
            `                x = cur;
            if (getComputedStyle(cur).position == "fixed" && !cur.offsetParent) {
                y = y || cur;
                if (getX) x = x || cur;
                break;
            }
            cur = cur.assignedSlot || cur.parentNode;`,
            "CodeMirror scroll walk",
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

  // File editing extensions sharing the runtime's CodeMirror implementation: merge
  // and autocomplete, which live in this optional package. The editor colours every
  // language with the syntax module (file-editor's editor.js). Their
  // state/view/language and Lezer imports bind to the core Leaf's composers use, so
  // extensions never mix CodeMirror identities.
  "file-editor": () => ({
    out: `${packageVendor("file-editor")}/extensions.esm.js`,
    entryPoints: [input("entries/file-editor/entry.mjs")],
    platform: "browser",
    target: "es2022",
    plugins: [
      bindTo(
        /^(?:@codemirror\/(?:state|view|language)|@lezer\/(?:highlight|common))$/,
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

  // Temml typesets the LaTeX in a page's `<code class="language-math">` as MathML the
  // browser draws itself (`runtime/readings/formulas.js`). Its sheet travels in the module as
  // text, as PhotoSwipe's does, so only a page that shows a formula loads it, and the
  // font that sheet names for primes and script capitals travels inside the sheet, so
  // an export needs no file beside the module.
  temml: () => ({
    out: `${assets}/vendor/temml.esm.js`,
    entryPoints: [input("entries/temml/entry.mjs")],
    loader: { ".css": "text" },
    banner: { js: `/*! Temml ${version("temml")} — MIT — temml.org */` },
    adapt: [
      {
        file: /temml\/dist\/Temml-Local\.css$/,
        edit: (source, at) =>
          seam(
            source,
            "url('Temml.woff2')",
            `url(data:font/woff2;base64,${readFileSync(
              path.join(path.dirname(at), "Temml.woff2"),
            ).toString("base64")})`,
            "Temml font",
          ),
      },
    ],
  }),

  // DOMPurify takes the script out of the HTML a Markdown file's preview draws
  // (`markdownFileFragment` in runtime/lib/markdown.js), which loads it only for a file
  // that holds HTML.
  dompurify: () => ({
    out: `${assets}/vendor/purify.esm.js`,
    entryPoints: [input("entries/dompurify/entry.mjs")],
  }),

  // Bundle only jsdiff's array comparison for the core browser runtime.
  jsdiff: () => ({
    out: `${assets}/vendor/jsdiff.esm.js`,
    entryPoints: [input("entries/jsdiff/entry.mjs")],
    banner: {
      js: `/*! jsdiff ${version("diff")} — BSD-3-Clause — https://github.com/kpdecker/jsdiff */`,
    },
  }),

  // DBSCAN groups screenshot fragments by their original neighborhoods.
  "density-clustering": () => ({
    out: `${packageVendor("default")}/density-clustering.esm.js`,
    entryPoints: [input("entries/density-clustering/entry.mjs")],
  }),

  // Observable Plot, which lf-chart hands a page's author. Nothing published is
  // loadable as it stands: `dist/plot.js` imports d3 by bare specifier,
  // `dist/plot.umd.min.js` reads a `d3` global the page would have to load first, and
  // a CDN's prebuilt ESM (jsdelivr's `+esm`) is smaller only because it imports d3
  // from a second URL, while the layer loads nothing from the network so a chart
  // draws offline and in an export. So this is Plot and the parts of d3 it reaches
  // for, in one module with no specifier left in it; vendoring d3 whole beside it
  // would be 100KB more and two files whose versions can drift apart. The whole of
  // Plot goes in, since an author writes the chart in Plot's own API.
  //
  // Which channels a tip says, how its `format` words each, and the lines it says
  // them in are decided inside Plot's tip mark, by functions Plot doesn't export.
  // The chart's preview says a point by those decisions, so Plot's published module,
  // `dist/plot.js`, exports them (`tipSources` and `tipRows` in the entry), each line
  // naming the channel it says.
  //
  // `build/@observablehq__plot.patch` has Plot's pointer pool rank only the pointers
  // that picked something. Unpatched, a pointer or facet that picks nothing outranks a
  // pick farther than its 40px reach, so a faceted chart with `tip: "x"` shows no tip,
  // and lf-chart's pick (chart-points.js `nearest`) no longer matches Plot's. The hunk
  // goes once Plot ships the fix (observablehq/plot#2475).
  plot: () => ({
    out: `${packageVendor("default")}/plot.esm.js`,
    entryPoints: [input("entries/plot/entry.mjs")],
    // Plot's, d3-array's and d3-delaunay's published modules carry these inside them.
    inlined: [
      "binary-search-bounds",
      "delaunator",
      "internmap",
      "interval-tree-1d",
      "isoformat",
      "robust-predicates",
    ],
    adapt: [
      {
        file: /@observablehq\/plot\/dist\/plot\.js$/,
        edit: (source) =>
          seam(
            seam(
              seam(
                source,
                "\nfunction getSourceChannels(channels, scales) {",
                "\nexport function getSourceChannels(channels, scales) {",
                "Plot tip sources",
              ),
              "\nfunction* formatChannels(i, index, channels, scales, values) {",
              "\nexport function* formatChannels(i, index, channels, scales, values) {",
              "Plot tip rows",
            ),
            "yield {",
            "yield {key,",
            "Plot tip row channel",
            4,
          ),
      },
    ],
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
        // A changed-word mark locates an edit only where the old and new lines are
        // mostly the same. Where most of a pair changed, marks cover most of both
        // lines and point at nothing, so the pair stays two plain rows. The cutoff is
        // delta's `--max-line-distance` default: the share of both lines' characters
        // the word diff removed or added.
        file: /@pierre\/diffs\/dist\/utils\/computeLineDiffRanges\.js$/,
        edit: (source) =>
          seam(
            source,
            '\tif (lineDiffType === "word-line") return',
            "\tlet leafChanged = 0;\n" +
              "\tfor (const item of lineDiff) if (item.added || item.removed) leafChanged += item.value.length;\n" +
              "\tif (leafChanged > 0.6 * (deletionLine.length + additionLine.length)) return NO_RANGES;\n" +
              '\tif (lineDiffType === "word-line") return',
            "Pierre changed-word distance",
          ),
      },
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
        file: /@pierre\/trees\/dist\/render\/scrollTarget\.js$/,
        // Trees measures its viewport with getBoundingClientRect, so a reveal target
        // can be fractional (138.16) where the browser holds the box at a device
        // pixel (138). Compared exactly, the target never equals where the box
        // stands, so each focus change writes a scroll that moves nothing and stops
        // one under way. A target within a pixel is where the box already stands.
        edit: (source) =>
          seam(
            seam(
              source,
              "return nextScrollTop === currentScrollTop ? null : nextScrollTop;",
              "return Math.abs(nextScrollTop - currentScrollTop) < 1 ? null : nextScrollTop;",
              "Trees scroll-target comparison",
              3,
            ),
            "return preservedScrollTop === currentScrollTop ? null : preservedScrollTop;",
            "return Math.abs(preservedScrollTop - currentScrollTop) < 1 ? null : preservedScrollTop;",
            "Trees preserved scroll-target comparison",
          ),
      },
      {
        file: /@pierre\/trees\/dist\/render\/FileTreeView\.js$/,
        // The viewport's clamp compares the box's scrollTop with a maximum computed
        // from the same fractional measure. At the list's end Chrome holds the box at
        // 1039 while the maximum comes out at 1038.94, so every scroll event and
        // model change there would write a scroll that moves nothing. A box within a
        // pixel of the maximum already stands at it.
        //
        // Upstream (beta.6 and 1.0.0) gives the root `role="tree"`, and the root also
        // holds the search field. A tree may own only tree items and groups, so the
        // field breaks the tree's role for assistive technology. The role moves to
        // the scroller, which holds only the rows; the root keeps the keys and the
        // layout, which `style.js`'s seam below moves with it.
        edit: (source) =>
          seam(
            seam(
              seam(
                source,
                "if (scrollElement.scrollTop > maxScrollTop) scrollElement.scrollTop = maxScrollTop;",
                "if (scrollElement.scrollTop - maxScrollTop >= 1) scrollElement.scrollTop = maxScrollTop;",
                "Trees viewport clamp",
              ),
              '\t\trole: "tree",\n\t\ttabIndex: -1,',
              "\t\ttabIndex: -1,",
              "Trees root role",
            ),
            '\t\t\t\t"data-file-tree-virtualized-scroll": "true",\n',
            '\t\t\t\t"data-file-tree-virtualized-scroll": "true",\n\t\t\t\trole: "tree",\n',
            "Trees scroller role",
          ),
      },
      {
        file: /@pierre\/trees\/dist\/style\.js$/,
        edit: (source) =>
          seam(
            source,
            '[role=\\"tree\\"] {',
            '[data-file-tree-virtualized-root=\\"true\\"] {',
            "Trees root layout",
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

  // Split chrome controls, the controls Leaf's widgets load with themselves (`views`)
  // and the catalogue a package's own module may import, sharing their dependency graph.
  // All three entry points register the same components once. The catalogue remains on
  // demand; the shared chunks are core payload because chrome also reads them. Lit binds
  // to the page's one copy (`build/lit.mjs`).
  webawesome: async () => ({
    out: `${packageVendor("default")}/webawesome.esm.js`,
    entryPoints: {
      "webawesome.esm": input("entries/webawesome/entry.mjs"),
      "webawesome-chrome": input("entries/webawesome/chrome.mjs"),
      "webawesome-views": input("entries/webawesome/views.mjs"),
    },
    outdir: `${assets}/vendor`,
    place: {
      [`${assets}/vendor/webawesome.esm.js`]: `${packageVendor("default")}/webawesome.esm.js`,
      [`${assets}/vendor/webawesome-views.js`]: `${packageVendor("default")}/webawesome-views.js`,
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
        file: /webawesome\/dist\/chunks\/chunk\.M22PYPNQ\.js$/,
        edit: patchTransitions,
      },
      // A radio group's arrow moves focus to the next radio in its row, which the user
      // already sees. Leaf places focus without scrolling (dom/focus.js, `focusDestination`),
      // and the focused-control landing margin made the native scroll move the chooser
      // under the arrow wherever a landing had left it at the window's top edge.
      {
        file: /webawesome\/dist\/chunks\/chunk\.G4XPRTJE\.js$/,
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
    inlined = [],
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
      // A page runs every bundle, and an element with id="process" is a global, so
      // `typeof process` there finds an object with no `env`. vscode-textmate reads
      // `process.env` whenever `process` is defined, and highlighting threw. Defining
      // `process` turns off esbuild's own `NODE_ENV` for minified browser builds, so
      // that is stated too.
      define: { process: "undefined", "process.env.NODE_ENV": '"production"' },
      metafile: true,
      write: false,
      logLevel: "warning",
      ...options,
    });
    for (const file of result.outputFiles) {
      const name = path.relative(root, file.path).split(path.sep).join("/");
      outputs.set(place[name] ?? name, Buffer.from(file.contents));
    }
    packages = bundledPackages(result.metafile, root, inlined);
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
 * The table of the grammars `syntax` bundles, a library module
 * (`runtime/lib/syntax-languages.js`): a literal import for each, so an export binds
 * it, and each name and alias Shiki gives a grammar, which a `language-…` class names,
 * read here so that identifying a block loads no grammar. Both come from this build,
 * which a page's grammars need anyway, so the browser doesn't read `$languages.names`
 * itself. `page check` reads the names too, as the one line of JSON
 * `syntaxLanguageNames` is written on (`leaf.records.markup_checks.markup.COLOURED_LANGUAGES`).
 * Beside them stands the shipped extension table, which `base/language-paths.js` starts
 * from until a page installs its composed one.
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
      "/** The shipped extension table, which a page's composition may change: a file's language on a page is `langForPath`'s, in the package API.\n" +
      ` * @type {Record<string, string>} */\n// prettier-ignore\nexport const syntaxLanguagePaths = ${JSON.stringify(languageDeclarations().paths)};\n`,
  );
}

/** Every bundle's outputs, and the library's syntax table, keyed by repository path. */
export async function vendorOutputs() {
  const built = await Promise.all(
    Object.values(bundles).map(async (spec) => bundle(await spec())),
  );
  return new Map([
    ...built.flatMap((outputs) => [...outputs]),
    [`${assets}/runtime/lib/syntax-languages.js`, await syntaxLoaders()],
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
