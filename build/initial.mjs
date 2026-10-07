/* Build the small classic initial renderers from their single package-owned source.
 * Delivery inlines only a renderer the document uses; the same committed IIFE can
 * also load as a module for a widget arriving in a later revision or thread. */
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { checkModule } from "./browser/shipped.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
export async function initialOutputs() {
  const outputs = new Map();
  const packages = path.join(root, "skills/leaf/packages");
  for (const item of (await readdir(packages, { withFileTypes: true }))
    .filter((item) => item.isDirectory())
    .sort((a, b) => a.name.localeCompare(b.name))) {
    const name = item.name;
    const directory = path.join(packages, name);
    if (!(await readdir(directory)).includes("registry.json")) continue;
    const registry = JSON.parse(
      await readFile(path.join(directory, "registry.json"), "utf8"),
    );
    const declared = [
      ...new Set(
        Object.values(registry).flatMap((entry) =>
          entry?.["x-initial"] ? [entry["x-initial"]] : [],
        ),
      ),
    ];
    if (!declared.length) continue;
    if (declared.length !== 1)
      throw new Error(`${name} needs a source entry for each initial bundle`);
    const entry = path.join(directory, "runtime/initial.js");
    const result = await build({
      entryPoints: [entry],
      bundle: true,
      format: "iife",
      write: false,
      minify: false,
      target: "es2022",
      legalComments: "inline",
    });
    const output = path.join("skills/leaf/packages", name, declared[0].slice(1));
    checkModule(result.outputFiles[0].text, output);
    outputs.set(output, Buffer.from(result.outputFiles[0].contents));
  }
  return outputs;
}
