/** Bundle the third-party stylesheets Leaf's own sheets import into ready files.
 *
 * Leaf's sheets need no build: layer composition and the serving runtime place each
 * `@import` of a file beside them inline (`leaf.layer.stylesheet`). A dependency's
 * sheet lives in `node_modules`, which an install doesn't have, so esbuild resolves its
 * imports here at contributor build time and the result is committed beside the sheet
 * that imports it. `build/browser/build.mjs` writes and checks these outputs with its
 * own.
 */
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** A control a page writes itself: one Leaf didn't build (`data-lf-offer`,
 * element-markers.js) and that doesn't stand in Leaf's chrome. */
const PAGE_CONTROL = ":not([data-lf-offer], .lf-chrome *)";

/** Source and output pairs, readable without build dependencies by the trusted
 * dependency publisher as well as the compiler. A third member takes regions of the
 * source onto faces instead of the whole sheet, in one projection after another
 * (`regions`, below).
 *
 * Web Awesome's native buttons, fields and choices draw two sets of controls: Leaf's
 * own, by their roles' classes, and a page's own, in the reading face's layer and
 * under its input (controls.css, "A page's own controls").
 * @type {[source: string, output: string, projections?: Projection[]][]} */
export const styleEntries = [
  [
    "node_modules/@awesome.me/webawesome/dist/styles/themes/default.css",
    "browser/styles/vendor/webawesome-theme.css",
  ],
  [
    "node_modules/@awesome.me/webawesome/dist/styles/native.css",
    "browser/styles/vendor/webawesome-native.css",
    [
      {
        faces: {
          "Checkboxes + Radios": { input: ".lf-choice > input" },
          Buttons: {
            button: ":is(.lf-btn, .lf-icon-action)",
            ".wa-plain": ":not(.lf-commit)",
            ".wa-outlined": ".lf-commit",
            ":disabled": ':is(:disabled, [aria-disabled="true"])',
            "::file-selector-button": null,
          },
          "Text Fields + Textareas + Selects": {
            input: "input.lf-ui",
            // A single-choice listbox (`size` over 1) keeps the browser's face: the
            // library draws every select but a multiple one as closed, a line tall.
            select: 'select.lf-ui:is([multiple], :not([size]), [size="0"], [size="1"])',
          },
        },
      },
      {
        faces: {
          "Checkboxes + Radios": { input: `label > input${PAGE_CONTROL}` },
          Buttons: {
            button: `button${PAGE_CONTROL}`,
            ".wa-plain": ':not([type="submit"])',
            ".wa-outlined": '[type="submit"]',
            ":disabled": ':is(:disabled, [aria-disabled="true"])',
            "::file-selector-button": null,
          },
          "Text Fields + Textareas + Selects": {
            input: `input${PAGE_CONTROL}`,
            // Leaf's own text boxes grow with their words (controls.css), which the
            // library's fixed-height field doesn't; a page's takes the library's.
            textarea: `textarea${PAGE_CONTROL}`,
            select: `select${PAGE_CONTROL}:is([multiple], :not([size]), [size="0"], [size="1"])`,
          },
        },
        within: ["@layer lf-reading-face", "@container style(--lf-reading-face: 1)"],
      },
    ],
  ],
];

export async function styleOutputs() {
  const outputs = new Map();
  for (const [source, output, projections] of styleEntries)
    outputs.set(
      output,
      Buffer.from(
        projections ? await regions(source, projections) : await sheet(source),
      ),
    );
  return outputs;
}

/** Leaf owns the type and the focus band of every control (surfaces.css), and its
 * motion (`--lf-motion-*`), so the rules taken from a dependency leave these
 * properties out. A transition would also report a control's old colour to whatever
 * reads it during the fade, as a test reading a state just set does. */
const LEAF_OWNS = /^(font|line-height|outline|transition)(-|$)/;

/** Values in the library's rules that Leaf sets otherwise. A select's chevron is drawn
 * in the library's cool grey, which its blend against the field's ground turned violet
 * on Leaf's warm grounds; a neutral grey blends to a neutral grey in either scheme. A
 * value the library no longer writes fails the build. */
const LEAF_SETS = { "rgb(180 180 200)": "rgb(180 180 180)" };

/** Regions of a dependency's sheet, each with its rules rewritten onto the faces that
 * take them, once for each projection. Web Awesome ships its styles for native
 * controls only in `native.css`, which restyles every element of a kind in the
 * document, so Leaf takes the regions for the controls it draws and names, for each
 * region, the faces each of the region's element types, classes and states stand for
 * (controls.css says which role takes which).
 *
 * A type or class a region's map doesn't name, and anything it maps to null, matches
 * no face: a selector that requires one goes, `:not()` of one goes from the selector
 * it stands in, and a selector that names nothing in the map goes too. Every rule then
 * weighs nothing (`:where()`), as the library's own sheet stands in its lowest layer,
 * and the rules keep the library's order, which alone ranks them among themselves. A
 * projection's rules stand within the at-rules it names, outermost first. shadow.css
 * imports the result after the layer's defaults for every control, such as
 * `.lf-ui-face`'s ink, which it replaces, and before controls.css, whose rules state
 * where Leaf departs from it. A region that moves or goes fails the build rather than
 * shipping an empty sheet.
 * @typedef {Record<string, Record<string, string | null>>} Faces
 * @typedef {{ faces: Faces, within?: string[] }} Projection
 * @param {string} source
 * @param {Projection[]} projections */
async function regions(source, projections) {
  const { readFile } = await import("node:fs/promises");
  const { transform, Features } = await import("lightningcss");
  const text = await readFile(resolve(root, source), "utf8");
  const parse = (/** @type {string} */ code, /** @type {any} */ visitor = undefined) =>
    transform({
      filename: source,
      code: Buffer.from(code),
      include: Features.Nesting,
      visitor,
    }).code.toString();
  /** @param {string} selector */
  const components = (selector) => {
    /** @type {any[]} */
    let found = [];
    parse(`${selector} {}`, {
      Rule: {
        style: (/** @type {any} */ rule) => void (found = rule.value.selectors[0]),
      },
    });
    return found;
  };
  let out = `/* @noformat Generated from ${source} by build/styles.mjs. */\n`;
  for (const { faces, within = [] } of projections) {
    let projected = "";
    for (const [name, select] of Object.entries(faces))
      projected += `\n/* Region "${name}" */\n${region(name, select)}\n`;
    out += within.reduceRight((rules, at) => `\n${at} {${rules}}\n`, projected);
  }
  for (const [from, to] of Object.entries(LEAF_SETS)) {
    if (!out.includes(from))
      throw new Error(`No ${from} in the regions taken from ${source}`);
    out = out.replaceAll(from, to);
  }
  return out;

  /** @param {string} name @param {Record<string, string | null>} select */
  function region(name, select) {
    const start = text.indexOf(`/* #region ${name} `);
    const end = text.indexOf("/* #endregion */", start);
    if (start < 0 || end < 0) throw new Error(`No region "${name}" in ${source}`);
    const map = new Map(
      Object.entries(select).map(([from, to]) => [
        from,
        to === null ? null : components(to),
      ]),
    );
    const flat = parse(text.slice(text.indexOf("\n", start) + 1, end));
    const rules = parse(flat, {
      Rule: {
        style(/** @type {any} */ rule) {
          const selectors = rule.value.selectors
            .map((/** @type {any[]} */ selector) => onFaces(selector, map))
            .filter(Boolean)
            .map(weightless);
          const kept = (/** @type {any[]} */ list) =>
            list.filter((d) => !LEAF_OWNS.test(declared(d)));
          const declarations = {
            declarations: kept(rule.value.declarations.declarations ?? []),
            importantDeclarations: kept(
              rule.value.declarations.importantDeclarations ?? [],
            ),
          };
          const count =
            declarations.declarations.length +
            declarations.importantDeclarations.length;
          if (!selectors.length || !count) return [];
          return revived({
            ...rule,
            value: { ...rule.value, selectors, declarations },
          });
        },
      },
      RuleExit: {
        media: (/** @type {any} */ rule) => (rule.value.rules.length ? undefined : []),
      },
    });
    return rules.trim();
  }
}

/** A selector rewritten onto the faces `map` names, or null where it names none of
 * them or requires an element no face is.
 * @param {any[]} selector
 * @param {Map<string, any[] | null>} map */
function onFaces(selector, map) {
  const rewritten = rewrite(selector, map);
  return rewritten?.named ? rewritten.parts : null;
}

/** @param {any[]} selector
 * @param {Map<string, any[] | null>} map
 * @returns {{ parts: any[], named: boolean } | null} */
function rewrite(selector, map) {
  /** @type {any[]} */
  const parts = [];
  let named = false;
  for (const part of selector) {
    const key =
      part.type === "type"
        ? part.name
        : part.type === "class"
          ? `.${part.name}`
          : part.type === "pseudo-class"
            ? `:${part.kind}`
            : part.type === "pseudo-element"
              ? `::${part.kind}`
              : null;
    const face = key === null ? undefined : map.get(key);
    if (face === null) return null;
    if (face) {
      parts.push(...structuredClone(face));
      named = true;
    } else if (part.type === "type" || part.type === "class") return null;
    else if (
      part.type === "pseudo-class" &&
      ["is", "where", "not"].includes(part.kind)
    ) {
      const within = part.selectors
        .map((/** @type {any[]} */ inner) => rewrite(inner, map))
        .filter(Boolean);
      // `:not()` of what matches no face holds for every face.
      if (part.kind === "not") {
        if (within.length)
          parts.push({ ...part, selectors: within.map((w) => w.parts) });
        continue;
      }
      if (!within.length) return null;
      parts.push({ ...part, selectors: within.map((w) => w.parts) });
      named ||= within.some((w) => w.named);
    } else if (
      (part.type === "pseudo-class" &&
        part.kind !== "has" &&
        (part.selectors || part.of)) ||
      (part.type === "pseudo-element" && part.selector)
    )
      // `:has()` asks about other elements, which no face names. Any other selector
      // argument, such as `::slotted()`'s, would need rewriting this code doesn't do,
      // so the build stops.
      throw new Error(`No rewrite for :${part.kind}() of selectors`);
    else parts.push(part);
  }
  return { parts, named };
}

/** The selector at no weight, its pseudo-element left outside `:where()`.
 * @param {any[]} selector */
function weightless(selector) {
  const at = selector.findIndex((part) => part.type === "pseudo-element");
  const head = at < 0 ? selector : selector.slice(0, at);
  const tail = at < 0 ? [] : selector.slice(at);
  return [{ type: "pseudo-class", kind: "where", selectors: [head] }, ...tail];
}

/** A rule handed back to lightningcss 1.33, which hands optional fields over as null
 * and refuses them back unless the key is absent.
 * @param {any} rule */
function revived(rule) {
  return JSON.parse(
    JSON.stringify(rule, (key, value) => (value === null ? undefined : value)),
  );
}

/** @param {any} declaration */
function declared(declaration) {
  return declaration.property === "unparsed" || declaration.property === "custom"
    ? (declaration.value.propertyId?.property ?? declaration.value.name ?? "")
    : declaration.property;
}

/** A dependency's whole sheet, bundled, with only its custom properties: the tokens its
 * components read. Its rules for the document, such as Web Awesome's root colour,
 * colour scheme and sans and its page frame, stay out, so a page without Leaf can
 * take the tokens at its root (`leaf.layer.portable_sheet`) and keep its own look.
 * @param {string} source */
async function sheet(source) {
  const { build } = await import("./esbuild.mjs");
  const result = await build({
    absWorkingDir: root,
    entryPoints: [source],
    bundle: true,
    write: false,
    metafile: true,
    logLevel: "silent",
    charset: "utf8",
    legalComments: "inline",
    plugins: [
      {
        name: "runtime-assets",
        setup(builder) {
          builder.onResolve({ filter: /.*/ }, (args) =>
            args.kind === "url-token" ? { path: args.path, external: true } : undefined,
          );
        },
      },
    ],
  });
  if (result.warnings.length)
    throw new Error(
      `Stylesheet build warnings in ${source}:\n${result.warnings.map((w) => w.text).join("\n")}`,
    );
  const deferredImports = Object.values(result.metafile.outputs)
    .flatMap((output) => output.imports)
    .filter((item) => item.kind === "import-rule");
  if (deferredImports.length)
    throw new Error(`Stylesheets must be complete at distribution: ${source}`);
  const { transform } = await import("lightningcss");
  const empty = (/** @type {any} */ rule) => (rule.value.rules.length ? undefined : []);
  const tokens = transform({
    filename: source,
    code: Buffer.from(result.outputFiles[0].text),
    visitor: {
      // A declaration kept is left untouched, since lightningcss 1.33 can't take back
      // every value it hands over, such as a colour in a custom property.
      Declaration: (/** @type {any} */ d) =>
        declared(d).startsWith("--") ? undefined : [],
      RuleExit: {
        style: (/** @type {any} */ rule) =>
          rule.value.declarations.declarations?.length ||
          rule.value.declarations.importantDeclarations?.length
            ? undefined
            : [],
        "layer-block": empty,
        media: empty,
        supports: empty,
      },
    },
  }).code.toString();
  return `/* @noformat Generated from ${source} by build/styles.mjs. */\n${tokens}`;
}
