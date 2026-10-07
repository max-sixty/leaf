/** Bundle the published browser runtime while preserving its public module URLs. */

import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { bundleRuntime, runtimeEntries } from "../build/runtime-bundle.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export async function bundleLayer(layerRoot, assetRoot, outputRoot = layerRoot) {
  const entries = [...runtimeEntries];
  for (const file of await readdir(join(layerRoot, "widgets"))) {
    if (file.endsWith(".js")) entries.push(`widgets/${file}`);
  }
  await bundleRuntime(layerRoot, entries, outputRoot, assetRoot);
}

export async function bundleSite(assets) {
  const manifest = JSON.parse(
    await readFile(join(assets, "_leaf", "site.json"), "utf8"),
  );
  for (const [route, page] of Object.entries(manifest.pages)) {
    const pageRoot = route === "/" ? assets : join(assets, route.slice(1));
    const revisions = join(pageRoot, "revisions");
    for (const revision of await readdir(revisions, { withFileTypes: true })) {
      if (!revision.isDirectory()) continue;
      await bundleLayer(
        join(revisions, revision.name),
        `${page.assets}/revisions/${revision.name}`,
      );
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await bundleSite(resolve(process.argv[2] ?? join(ROOT, ".tmp", "site-assets")));
}
