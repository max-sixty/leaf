/** Prepared kernels share one state instance with native package modules. */
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

import { bundleDistribution } from "./runtime-bundle.mjs";

test("prepared kernels preserve native packages, shared state, and stampable generation", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "leaf-install-bundle-"));
  const layer = join(temporary, "input");
  const output = join(temporary, "output");
  const sources = {
    "leaf.js":
      'export { state } from "./runtime/state.js"; export const annotations = () => import("./runtime/annotation-overlay/index.js"); export const widget = () => import("./widgets/custom.js");',
    "runtime/state.js": "export const state = { clicks: 0, annotations: false };",
    "runtime/vendor-bridge.js": 'export { state } from "./state.js";',
    "runtime/widget-api.js": 'export { state } from "./state.js";',
    "runtime/check-api.js": 'export { state } from "./state.js";',
    "runtime/interaction-gallery-frame.js": 'export { state } from "./state.js";',
    "runtime/media.js": 'export { state } from "./state.js";',
    "runtime/layer-client.js":
      'export { layerGeneration } from "./layer-generation.js";',
    "runtime/layer-generation.js":
      'export const layerGeneration = "__LEAF_LAYER_GENERATION__";',
    "runtime/annotation-overlay/index.js":
      'import { state } from "/runtime/state.js"; export { state }; state.annotations = true; export const vendor = () => import("../../vendor/example.js");',
    "runtime/bootstrap.js": "(() => { window.boot = true; })();",
    "runtime/prepaint.js": "(() => { window.paint = true; })();",
    "runtime/offline-delivery.js": "(() => { window.offline = true; })();",
    "runtime/image-difference.js": "export const compareImages = () => [];",
    "widgets/custom.js":
      'import { state } from "/runtime/widget-api.js"; state.clicks += 1;',
    "vendor/example.js": 'export { state } from "/runtime/vendor-bridge.js";',
  };
  try {
    for (const [path, source] of Object.entries(sources)) {
      await mkdir(dirname(join(layer, path)), { recursive: true });
      await writeFile(join(layer, path), source);
    }
    await bundleDistribution(layer, output);
    await writeFile(join(output, "package.json"), '{"type":"module"}');

    const leaf = await import(pathToFileURL(join(output, "leaf.js")));
    const api = await import(pathToFileURL(join(output, "runtime/widget-api.js")));
    assert.equal(leaf.state.annotations, false);
    const annotations = await leaf.annotations();
    assert.equal(leaf.state.annotations, true);
    const bridge = await import(
      pathToFileURL(join(output, "runtime/vendor-bridge.js"))
    );
    assert.equal(api.state, leaf.state);
    assert.equal(bridge.state, leaf.state);
    assert.equal(annotations.state, leaf.state);
    api.state.clicks += 1;
    assert.equal(annotations.state.clicks, 1);

    const files = await readdir(output, { recursive: true });
    assert.equal(
      files.some((path) => path.startsWith("widgets/")),
      false,
    );
    assert.equal(
      files.some((path) => path.startsWith("vendor/")),
      false,
    );
    assert.match(
      await readFile(join(output, "leaf.js"), "utf8"),
      /import\("\/widgets\/custom.js"\)/,
    );
    assert.match(
      await readFile(join(output, "runtime/annotation-overlay/index.js"), "utf8"),
      /import\("\/vendor\/example.js"\)/,
    );
    assert.match(
      await readFile(join(output, "runtime/layer-client.js"), "utf8"),
      /from"\/runtime\/layer-generation.js"/,
    );
    for (const path of [
      "runtime/layer-generation.js",
      "runtime/bootstrap.js",
      "runtime/prepaint.js",
      "runtime/offline-delivery.js",
      "runtime/image-difference.js",
    ])
      assert.equal(await readFile(join(output, path), "utf8"), sources[path]);
    const javascript = await Promise.all(
      files
        .filter((path) => path.endsWith(".js"))
        .map((path) => readFile(join(output, path), "utf8")),
    );
    assert.equal(
      javascript.join("\n").split('"__LEAF_LAYER_GENERATION__"').length - 1,
      1,
    );
  } finally {
    await rm(temporary, { recursive: true });
  }
});
