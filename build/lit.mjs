/**
 * The page's one Lit. Pages with any initial producer inline
 * `vendor/lit-initial.js` and map `/vendor/lit.js` to the shared namespace facade.
 * Other pages load the ordinary module implementation at `/vendor/lit.js`.
 * `build/browser/build.mjs` builds both from Lit's public exports, shaped like Lit's
 * own `lit-all` bundle. Static-html's
 * template tags would collide there with the ordinary `html`, `svg` and `mathml`, so
 * they get a `static` prefix. A bundle that carries Lit-based components
 * imports Lit through `bindToVendoredLit`, which reverses that renaming, so a page
 * registers one LitElement, one template cache, and one version. Both directions read
 * the same naming rule and the export list Lit itself publishes.
 */
import { readFileSync } from "node:fs";

/** The layer path of the page's one Lit. */
export const litPath = "vendor/lit.js";
/** The classic implementation delivery inlines when an early producer needs it. */
export const initialLitPath = "vendor/lit-initial.js";
/** Module bindings for a page that already initialized Lit before parsing its body. */
export const sharedLitPath = "vendor/lit-shared.js";
/** Shared by the classic implementation, early producers and the module facade. */
export const litGlobal = "document.documentElement.lfInitial.lit";

/** Static-html's template tags, prefixed to distinguish the ordinary tags. */
const staticTags = ["html", "svg", "mathml"];

/** Static-html's exports, the renamed tags first, as `[published, inLit]` pairs. */
async function staticExports() {
  const published = Object.keys(await import("lit/static-html.js"));
  for (const tag of staticTags)
    if (!published.includes(tag)) throw new Error(`lit/static-html.js lacks ${tag}`);
  return [
    ...staticTags.map((tag) => [tag, `static${tag[0].toUpperCase()}${tag.slice(1)}`]),
    ...published.filter((name) => !staticTags.includes(name)).map((n) => [n, n]),
  ];
}

const specifiers = (pairs) =>
  pairs.map(([from, to]) => (from === to ? from : `${from} as ${to}`)).join(", ");

// Public modules that can share one namespace. Static-html is exported separately
// under distinct tag names; polyfill support targets browsers older than Leaf's.
function litModules() {
  const { exports } = JSON.parse(
    readFileSync(new URL("../node_modules/lit/package.json", import.meta.url), "utf8"),
  );
  return Object.keys(exports)
    .filter(
      (subpath) => !["./static-html.js", "./polyfill-support.js"].includes(subpath),
    )
    .map((subpath) => `lit${subpath.slice(1)}`);
}

/** All names the shared namespace exposes, including static-html's renamed tags. */
async function litExportNames() {
  const modules = await Promise.all(litModules().map((name) => import(name)));
  const names = new Set(modules.flatMap((module) => Object.keys(module)));
  for (const [, name] of await staticExports()) names.add(name);
  return [...names].sort();
}

/** Named bindings to the initialized instance; importing these creates no second Lit. */
async function litBindings() {
  const names = (await litExportNames()).join(", ");
  return `const { ${names} } = ${litGlobal};\nexport { ${names} };\n`;
}

/** The later facade: module bindings to the instance the page initialized. */
export async function litFacade() {
  return await litBindings();
}

/** Early bundles bind to the initialized namespace without copying any Lit code. */
export async function bindToInitialLit() {
  const bindings = await litBindings();
  const reverse = (await staticExports()).map(([from, to]) => [to, from]);
  return {
    name: "leaf-initial-lit",
    setup(builder) {
      builder.onResolve(
        { filter: /^(lit(?:\/|$)|\/vendor\/lit\.js$)/ },
        ({ path }) => ({
          path: path === "lit/static-html.js" ? "static" : "lit",
          namespace: "leaf-initial-lit",
        }),
      );
      builder.onLoad({ filter: /.*/, namespace: "leaf-initial-lit" }, ({ path }) => ({
        contents:
          path === "static"
            ? `const { ${reverse.map(([from, to]) => (from === to ? from : `${from}: ${to}`)).join(", ")} } = ${litGlobal};\nexport { ${reverse.map(([, to]) => to).join(", ")} };`
            : bindings,
        loader: "js",
      }));
    },
  };
}

/**
 * The source namespace bundled into the classic Lit implementation.
 *
 * Star exports would make static-html's tags ambiguous with the ordinary ones and
 * drop both, so that module is exported by name instead; the polyfill module patches
 * browsers older than any Leaf supports.
 */
export async function litNamespace() {
  const stars = litModules().map((specifier) => `export * from "${specifier}";`);
  return [
    ...stars,
    `export { ${specifiers(await staticExports())} } from "lit/static-html.js";`,
  ].join("\n");
}

/**
 * An esbuild plugin binding every Lit import to `/vendor/lit.js`.
 *
 * Imports use the page's public namespace directly; the importing package's local
 * Lit is never bundled or loaded.
 */
export async function bindToVendoredLit() {
  const reverse = (await staticExports()).map(([from, to]) => [to, from]);
  return {
    name: "leaf-vendored-lit",
    setup(build) {
      const vendored = new RegExp(`^/${litPath.replaceAll(".", "\\.")}$`);
      build.onResolve({ filter: vendored }, ({ path: specifier }) => ({
        path: specifier,
        external: true,
      }));
      build.onResolve({ filter: /^lit(\/|$)/ }, ({ path: specifier }) =>
        specifier === "lit/static-html.js"
          ? { path: "static-html", namespace: "leaf-vendored-lit" }
          : { path: `/${litPath}`, external: true },
      );
      build.onLoad({ filter: /.*/, namespace: "leaf-vendored-lit" }, () => ({
        contents: `export { ${specifiers(reverse)} } from "/${litPath}";`,
      }));
    },
  };
}
