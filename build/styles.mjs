/** Bundle the third-party stylesheets Leaf's own sheets import into ready files, and
 * draw Leaf's control faces onto the controls a page writes itself.
 *
 * Leaf's sheets need no build: layer composition and the serving runtime place each
 * `@import` of a file beside them inline (`leaf.source.layer.stylesheet`). A dependency's
 * sheet lives in `node_modules`, which an install doesn't have, so esbuild resolves its
 * imports here at contributor build time and the result is committed beside the sheet
 * that imports it. The faces of a page's own controls are a projection of Leaf's,
 * generated here from the rules that draw Leaf's own (`regions`, below), so an edit to
 * one of those regions of controls.css takes `pnpm run build:browser` to reach a page's
 * controls, and `pnpm run check:browser` fails until it has. `build/browser/build.mjs`
 * writes and checks these outputs with its own.
 */
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const NATIVE = "node_modules/@awesome.me/webawesome/dist/styles/native.css";

/** Leaf owns the type and the focus band of every control (control-face.css,
 * surfaces.css), and its motion (`--lf-motion-*`), so the rules taken from a dependency
 * leave these properties out. A transition would also report a control's old colour to whatever
 * reads it during the fade, as a test reading a state just set does. */
const LEAF_OWNS = /^(font|line-height|outline|transition)(-|$)/;

/** A control a page writes itself: one Leaf didn't build (`data-lf-offer`,
 * lib/controls.js) and that doesn't stand in Leaf's chrome. */
const PAGE_CONTROL = ":not([data-lf-offer], .lf-chrome *)";

/** Leaf's control faces, as a page's own controls wear them: a word is a button, the
 * commit a submit button, HTML's word for the action that commits a form, a choice a
 * label holding a radio or checkbox, and a field a text field or select. A symbol has
 * no page twin. */
const LEAF_ONTO_PAGE = {
  ".lf-btn": `button${PAGE_CONTROL}`,
  ".lf-icon-action": null,
  ".lf-commit": '[type="submit"]',
  ".lf-choice": `label${PAGE_CONTROL}:has(input:is([type="checkbox"], [type="radio"]):not([data-lf-offer]))`,
  ".lf-ui": PAGE_CONTROL,
  input: "input",
  select: "select",
};

/** Source and output pairs, readable without build dependencies by the trusted
 * dependency publisher as well as the compiler. A third member takes regions of a
 * source onto faces instead of the whole sheet, in one projection after another
 * (`regions`, below).
 *
 * Web Awesome's native buttons, fields and choices draw two sets of controls: Leaf's
 * own, by their roles' classes, and a page's own (controls.css, "The faces of Leaf's
 * control roles"), which also take Leaf's departures from the library, the regions of
 * controls.css that draw them. A page's stand under markup's reading face, the theme's
 * input (reading.css), at no weight, so any rule of the page's own outranks them. They
 * stand in the tier Leaf's own faces do rather than a layer below it, where the
 * layer's band (surfaces.css) would outrank the rule that moves a choice's ring from
 * its mark to its label.
 * @type {[source: string, output: string, projections?: Projection[]][]} */
export const styleEntries = [
  [
    "node_modules/@awesome.me/webawesome/dist/styles/themes/default.css",
    "browser/styles/vendor/webawesome-theme.css",
  ],
  [
    NATIVE,
    "browser/styles/vendor/webawesome-native.css",
    [
      {
        drops: LEAF_OWNS,
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
    ],
  ],
  [
    NATIVE,
    "browser/styles/vendor/page-controls.css",
    [
      {
        drops: LEAF_OWNS,
        faces: {
          "Checkboxes + Radios": { input: `label input${PAGE_CONTROL}` },
          Buttons: {
            button: `button${PAGE_CONTROL}`,
            ".wa-plain": ':not([type="submit"])',
            ".wa-outlined": '[type="submit"]',
            ":disabled": ':is(:disabled, [aria-disabled="true"])',
            "::file-selector-button": null,
          },
          "Text Fields + Textareas + Selects": {
            input: `input${PAGE_CONTROL}`,
            select: `select${PAGE_CONTROL}:is([multiple], :not([size]), [size="0"], [size="1"])`,
          },
        },
        within: ["@container style(--lf-reading-face: 1)"],
      },
      {
        source: "browser/styles/components/controls.css",
        faces: Object.fromEntries(
          ["Word", "Choice", "Toggle", "Field"].map((name) => [
            `Face: ${name}`,
            LEAF_ONTO_PAGE,
          ]),
        ),
        within: ["@container style(--lf-reading-face: 1)"],
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

/** Values in the library's rules that Leaf sets otherwise. A select's chevron is drawn
 * in the library's cool grey, which its blend against the field's ground turned violet
 * on Leaf's warm grounds; a neutral grey blends to a neutral grey in either scheme. A
 * value the library no longer writes fails the build. */
const LEAF_SETS = { "rgb(180 180 200)": "rgb(180 180 180)" };

/** Regions of a sheet, each with its rules rewritten onto the faces that take them,
 * once for each projection. Web Awesome ships its styles for native controls only in
 * `native.css`, which restyles every element of a kind in the document, so Leaf takes
 * the regions for the controls it draws and names, for each region, the faces each of
 * the region's element types, classes and states stand for (controls.css says which
 * role takes which). A projection may read another source's regions, as a page's
 * controls read the regions of controls.css that draw Leaf's faces, and may drop the
 * properties Leaf owns from a dependency's rules.
 *
 * A type or class a region's map doesn't name, and anything it maps to null, matches
 * no face: a selector that requires one goes, `:not()` of one goes from the selector
 * it stands in, and a selector that names nothing in the map goes too. Every rule then
 * weighs nothing (`:where()`), as the library's own sheet stands in its lowest layer,
 * and the rules keep their source's order, which alone ranks them among themselves. A
 * projection's rules stand within the at-rules it names, outermost first. shadow.css
 * imports the results after the layer's defaults for every control, such as
 * `.lf-ui-face`'s ink, which they replace, and before controls.css, whose rules state
 * where Leaf departs from the library. A region that moves or goes fails the build
 * rather than shipping an empty sheet.
 * @typedef {Record<string, Record<string, string | null>>} Faces
 * @typedef {{ faces: Faces, source?: string, drops?: RegExp, within?: string[] }} Projection
 * @param {string} source
 * @param {Projection[]} projections */
async function regions(source, projections) {
  const { readFile } = await import("node:fs/promises");
  const { transform, Features } = await import("lightningcss");
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
  const sources = [...new Set(projections.map((p) => p.source ?? source))];
  let out = `/* Generated from ${sources.join(" and ")} by build/styles.mjs. */\n`;
  for (const { faces, source: from = source, drops, within = [] } of projections) {
    const text = await readFile(resolve(root, from), "utf8");
    let projected = "";
    for (const [name, select] of Object.entries(faces))
      projected += `\n/* Region "${name}" */\n${region(text, from, name, select, drops)}\n`;
    out += within.reduceRight((rules, at) => `\n${at} {${rules}}\n`, projected);
  }
  for (const [from, to] of Object.entries(LEAF_SETS)) {
    if (!out.includes(from))
      throw new Error(`No ${from} in the regions taken from ${source}`);
    out = out.replaceAll(from, to);
  }
  return out;

  /** @param {string} text @param {string} from @param {string} name
   * @param {Record<string, string | null>} select @param {RegExp | undefined} drops */
  function region(text, from, name, select, drops) {
    const start = text.indexOf(`/* #region ${name} `);
    const end = text.indexOf("/* #endregion */", start);
    if (start < 0 || end < 0) throw new Error(`No region "${name}" in ${from}`);
    const map = new Map(
      Object.entries(select).map(([key, to]) => [
        key,
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
            .flatMap(spread)
            .map(weightless);
          const kept = (/** @type {any[]} */ list) =>
            drops ? list.filter((d) => !drops.test(declared(d))) : list;
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

/** The selector once for each alternative of an `:is()` or `:where()` that alone could
 * key its compound, as a face's list of classes does (`:is(.lf-btn, .lf-icon-action)`).
 * A compound keyed by no class, id, type or attribute files its rule under none, and
 * Chromium tests such a rule against every element on every restyle
 * (browser/AGENTS.md, "A rule costs only the elements it could style"); one
 * alternative each keys it.
 * Every rule here weighs nothing (`weightless`), so the copies rank as the one did.
 * @param {any[]} written
 * @returns {any[][]} */
function spread(written) {
  const selector = inlined(written);
  for (const [at, part] of selector.entries()) {
    if (!isList(part) || part.selectors.length < 2) continue;
    if (compoundAt(selector, at).some(isKey)) continue;
    if (!part.selectors.every((/** @type {any[]} */ each) => subject(each).some(isKey)))
      continue;
    return part.selectors.flatMap((/** @type {any[]} */ each) =>
      spread([
        ...selector.slice(0, at),
        { ...part, selectors: [each] },
        ...selector.slice(at + 1),
      ]),
    );
  }
  return [selector];
}

/** The selector with each `:is()` or `:where()` of one compound written into the
 * compound it stands in, as a nested rule's parent comes to stand once a face replaces
 * the types it named (`:is(:is(.lf-btn, .lf-icon-action))`). Weightless, it matches
 * as it did.
 * @param {any[]} selector
 * @returns {any[]} */
function inlined(selector) {
  return selector.flatMap((part, at) => {
    if (!isList(part) || part.selectors.length !== 1) return [part];
    const [inner] = part.selectors;
    const typed = inner.some(
      (/** @type {any} */ each) => each.type === "type" || each.type === "universal",
    );
    // A type stands first in its compound.
    const first = at === 0 || selector[at - 1].type === "combinator";
    return inner.some((/** @type {any} */ each) => each.type === "combinator") ||
      (typed && !first)
      ? [part]
      : inlined(inner);
  });
}

/** @param {any} part */
function isList(part) {
  return part.type === "pseudo-class" && ["is", "where"].includes(part.kind);
}

/** Whether a simple selector keys its compound: a class, id, type or attribute, or an
 * `:is()` or `:where()` of one selector whose subject has one.
 * @param {any} part */
function isKey(part) {
  return (
    ["class", "id", "type", "attribute"].includes(part.type) ||
    (isList(part) &&
      part.selectors.length === 1 &&
      subject(part.selectors[0]).some(isKey))
  );
}

/** The compound a selector's part stands in.
 * @param {any[]} selector
 * @param {number} at */
function compoundAt(selector, at) {
  let start = at;
  while (start > 0 && selector[start - 1].type !== "combinator") start--;
  let end = at;
  while (end < selector.length && selector[end].type !== "combinator") end++;
  return selector.slice(start, end);
}

/** A selector's subject compound.
 * @param {any[]} selector */
function subject(selector) {
  return compoundAt(selector, selector.length - 1);
}

/** The selector at no weight, each compound in a `:where()` of its own, so a compound
 * that keys the rule or an ancestor's still does (`spread`), and its pseudo-element
 * left outside.
 * @param {any[]} selector */
function weightless(selector) {
  const at = selector.findIndex((part) => part.type === "pseudo-element");
  const head = at < 0 ? selector : selector.slice(0, at);
  const tail = at < 0 ? [] : selector.slice(at);
  /** @type {any[]} */
  const out = [];
  let compound = [];
  for (const part of [...head, null]) {
    if (part && part.type !== "combinator") {
      compound.push(part);
      continue;
    }
    out.push({ type: "pseudo-class", kind: "where", selectors: [compound] });
    if (part) out.push(part);
    compound = [];
  }
  return [...out, ...tail];
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
 * take the tokens at its root (`leaf.source.layer.portable_sheet`) and keep its own look.
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
  return `/* Generated from ${source} by build/styles.mjs. */\n${tokens}`;
}
