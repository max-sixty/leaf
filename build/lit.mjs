/**
 * The page's one Lit, `/vendor/lit.js`, and how a bundle binds its Lit imports to it.
 *
 * `build/browser/build.mjs` builds `lit.js` from `litNamespace()`: every public Lit
 * module in one namespace, shaped like Lit's own `lit-all` bundle. Static-html's
 * template tags would collide there with the ordinary `html`, `svg` and `mathml`, so
 * they go by the names in `staticTags`. A bundle that carries Lit-based components
 * imports Lit through `bindToVendoredLit`, which reverses that renaming, so a page
 * registers one LitElement, one template cache, and one version. Both directions read
 * the one table and the export list Lit itself publishes.
 */
import { readFileSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);

/** The layer path of the page's one Lit. */
export const litPath = "vendor/lit.js";

/** Static-html's template tags, and the names `lit.js` gives them. */
const staticTags = { html: "staticHtml", svg: "staticSvg", mathml: "staticMathml" };

/** Static-html's exports, the renamed tags first, as `[published, inLit]` pairs. */
async function staticExports() {
  const published = Object.keys(await import("lit/static-html.js"));
  for (const tag of Object.keys(staticTags))
    if (!published.includes(tag)) throw new Error(`lit/static-html.js lacks ${tag}`);
  return [
    ...Object.entries(staticTags),
    ...published.filter((name) => !Object.hasOwn(staticTags, name)).map((n) => [n, n]),
  ];
}

const specifiers = (pairs) =>
  pairs.map(([from, to]) => (from === to ? from : `${from} as ${to}`)).join(", ");

/**
 * The source of `lit.js`.
 *
 * Star exports would make static-html's tags ambiguous with the ordinary ones and
 * drop both, so that module is exported by name instead; the polyfill module patches
 * browsers older than any Leaf supports.
 */
export async function litNamespace() {
  const { exports } = JSON.parse(
    readFileSync(new URL("../node_modules/lit/package.json", import.meta.url)),
  );
  const stars = Object.keys(exports)
    .filter(
      (subpath) => !["./static-html.js", "./polyfill-support.js"].includes(subpath),
    )
    .map((subpath) => `export * from "lit${subpath.slice(1)}";`);
  return [
    ...stars,
    `export { ${specifiers(await staticExports())} } from "lit/static-html.js";`,
  ].join("\n");
}

/**
 * An esbuild plugin binding every Lit import to `/vendor/lit.js`.
 *
 * Binding is sound only where the importing package resolves the Lit `lit.js` was
 * built from, so a package that resolves another copy fails the build.
 */
export async function bindToVendoredLit() {
  const reverse = (await staticExports()).map(([from, to]) => [to, from]);
  const leafLit = realpathSync(require.resolve("lit"));
  const checked = new Set();
  return {
    name: "leaf-vendored-lit",
    setup(build) {
      const vendored = new RegExp(`^/${litPath.replaceAll(".", "\\.")}$`);
      build.onResolve({ filter: vendored }, ({ path: specifier }) => ({
        path: specifier,
        external: true,
      }));
      build.onResolve({ filter: /^lit(\/|$)/ }, ({ path: specifier, resolveDir }) => {
        if (!checked.has(resolveDir)) {
          const lit = createRequire(path.join(resolveDir, "_")).resolve("lit");
          if (realpathSync(lit) !== leafLit)
            throw new Error(`${resolveDir} resolves another Lit than ${litPath}`);
          checked.add(resolveDir);
        }
        return specifier === "lit/static-html.js"
          ? { path: "static-html", namespace: "leaf-vendored-lit" }
          : { path: `/${litPath}`, external: true };
      });
      build.onLoad({ filter: /.*/, namespace: "leaf-vendored-lit" }, () => ({
        contents: `export { ${specifiers(reverse)} } from "/${litPath}";`,
      }));
    },
  };
}
