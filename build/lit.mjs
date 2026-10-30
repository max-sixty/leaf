/**
 * The page's one Lit, an ordinary ES module shared by runtime and packages.
 * Packages bind every Lit import to this namespace rather than bundling their
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
    readFileSync(new URL("../node_modules/lit/package.json", import.meta.url)),
  );
  return Object.keys(exports)
    .filter(
      (subpath) => !["./static-html.js", "./polyfill-support.js"].includes(subpath),
    )
    .map((subpath) => `lit${subpath.slice(1)}`);
}

/**
 * The shared Lit namespace.
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
