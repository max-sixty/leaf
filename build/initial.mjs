/* Build the small classic initial renderers from their single package-owned source.
 * Delivery inlines only a renderer the document uses; the same committed IIFE can
 * also load as a module for a widget arriving in a later revision or thread.
 *
 * A producer a widget also draws with off Leaf lives beside the widget and imports the
 * portable helpers by their served path (`/runtime/portable-api.js`), as the widget
 * does. Here those resolve to the runtime's sources, bundled for only the names the
 * producer uses: none of them has a side effect a producer depends on, and Lit binds to
 * the page's initialized instance as every producer's does. */
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "./esbuild.mjs";
import { bindToInitialLit } from "./lit.mjs";
import { checkModule } from "./browser/shipped.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
const runtimeSources = {
  name: "leaf-runtime-sources",
  setup(builder) {
    builder.onResolve({ filter: /^\/runtime\// }, ({ path: specifier }) => ({
      path: path.join(root, "browser", specifier),
      sideEffects: false,
    }));
    // What the producer leaves out may load vendor modules; one it uses may not.
    builder.onResolve({ filter: /^\/vendor\// }, ({ path: specifier }) => ({
      path: specifier,
      external: true,
    }));
    builder.onResolve({ filter: /^\.\.?\// }, ({ path: specifier, importer }) =>
      importer.startsWith(path.join(root, "browser", "runtime"))
        ? { path: path.resolve(path.dirname(importer), specifier), sideEffects: false }
        : undefined,
    );
  },
};
export async function initialOutputs() {
  const outputs = new Map();
  const packages = path.join(root, "packages");
  for (const item of (await readdir(packages, { withFileTypes: true }))
    .filter((item) => item.isDirectory())
    .sort((a, b) => a.name.localeCompare(b.name))) {
    const name = item.name;
    const directory = path.join(packages, name);
    if (!(await readdir(directory)).includes("registry.json")) continue;
    const registry = JSON.parse(
      await readFile(path.join(directory, "registry.json"), "utf8"),
    );
    // Each tag's renderer is its own bundle, from `initial/<tag>.js`, so a document
    // inlines only the renderers of the widgets it holds.
    for (const [tag, entry] of Object.entries(registry)) {
      if (!entry?.["x-initial"]) continue;
      const output = path.join("packages", name, entry["x-initial"].slice(1));
      if (outputs.has(output))
        throw new Error(`${output} is more than one tag's bundle`);
      const result = await build({
        entryPoints: [path.join(directory, "initial", `${tag}.js`)],
        bundle: true,
        plugins: [await bindToInitialLit(), runtimeSources],
        format: "iife",
        write: false,
        minify: false,
        target: "es2022",
        legalComments: "inline",
      });
      checkModule(result.outputFiles[0].text, output);
      outputs.set(output, Buffer.from(result.outputFiles[0].contents));
    }
  }
  return outputs;
}
