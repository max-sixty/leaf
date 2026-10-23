/* Build the small classic initial renderers from their single package-owned source.
 * Delivery inlines only a renderer the document uses; the same committed IIFE can
 * also load as a module for a widget arriving in a later revision or thread. */
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "./esbuild.mjs";
import { bindToInitialSolid, initialSolidPath } from "./solid.mjs";
import { checkModule } from "./browser/shipped.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
export async function initialOutputs() {
  const outputs = new Map();
  const dependencies = {};
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
        metafile: true,
        plugins: [await bindToInitialSolid()],
        format: "iife",
        write: false,
        minify: false,
        target: "es2022",
        legalComments: "inline",
      });
      checkModule(result.outputFiles[0].text, output);
      outputs.set(output, Buffer.from(result.outputFiles[0].contents));
      if (
        Object.keys(result.metafile.inputs).some((input) =>
          input.startsWith("leaf-initial-solid:"),
        )
      )
        dependencies[entry["x-initial"]] = [`/${initialSolidPath}`];
    }
  }
  // Delivery reads the build's dependency facts; it never names widget families.
  outputs.set(
    "browser/vendor/initial-dependencies.json",
    Buffer.from(JSON.stringify(dependencies) + "\n"),
  );
  return outputs;
}
