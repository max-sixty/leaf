/** The committed kernel shares one state instance with native package modules. */
import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

import { kernelOutputs } from "./runtime-bundle.mjs";

/** The runtime a Leaf serves with the kernel: the source minus what it replaces. */
async function vendor(layer, kernel, output) {
  await cp(layer, output, { recursive: true });
  const record = JSON.parse(kernel.get("kernel.json"));
  for (const path of record.replaces) await rm(join(output, path));
  for (const [path, bytes] of kernel) {
    if (path === "kernel.json") continue;
    await mkdir(dirname(join(output, path)), { recursive: true });
    await writeFile(join(output, path), bytes);
  }
  return record;
}

test("the kernel preserves native packages and shared state", async () => {
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
    "runtime/annotation-overlay/check-api.js": 'export { state } from "../state.js";',
    "runtime/media.js":
      'export { state } from "./state.js"; export { rendered } from "./framework.js";',
    "runtime/layer-client.js": 'export { state } from "./state.js";',
    "runtime/annotation-overlay/index.js":
      'import { state } from "../state.js"; export { state }; state.annotations = true; export const vendor = () => import("../../vendor/example.js");',
    "runtime/bootstrap.js": "(() => { window.boot = true; })();",
    "widgets/custom.js":
      'import { state } from "/runtime/widget-api.js"; state.clicks += 1;',
    "vendor/example.js": 'export { state } from "/runtime/vendor-bridge.js";',
    "vendor/lit.js": "export const html = (strings) => strings.join('');\n",
    "vendor/signals-core.js": "export const signal = (value) => ({ value });\n",
    "runtime/framework.js": 'export { rendered } from "./framework/render.js";\n',
    "runtime/framework/render.js":
      'import { html } from "/vendor/lit.js";\nimport { signal } from "/vendor/signals-core.js";\nimport { state } from "../state.js";\n\nexport const rendered = () => html([signal(state).value]);\n',
  };
  try {
    for (const [path, source] of Object.entries(sources)) {
      await mkdir(dirname(join(layer, path)), { recursive: true });
      await writeFile(join(layer, path), source);
    }
    const kernel = await kernelOutputs(layer);
    // A rebuild of the same modules reproduces the committed bytes.
    assert.deepEqual(await kernelOutputs(layer), kernel);
    const record = await vendor(layer, kernel, output);
    await writeFile(join(output, "package.json"), '{"type":"module"}');

    const leaf = await import(pathToFileURL(join(output, "leaf.js")));
    const api = await import(pathToFileURL(join(output, "runtime/widget-api.js")));
    const checks = await import(pathToFileURL(join(output, "runtime/check-api.js")));
    const overlayChecks = await import(
      pathToFileURL(join(output, "runtime/annotation-overlay/check-api.js"))
    );
    assert.equal(leaf.state.annotations, false);
    assert.equal(checks.state, leaf.state);
    assert.equal(overlayChecks.state, leaf.state);
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

    // The kernel is runtime modules and chunks named after their modules; it
    // absorbs the framework and its signals and leaves widgets, upstream vendor
    // modules, and the classic scripts nothing imports native.
    assert.deepEqual([...kernel.keys()].sort(), [
      "kernel.json",
      "leaf.js",
      "runtime/annotation-overlay/check-api.js",
      "runtime/bundle-annotation-overlay.js",
      "runtime/bundle-state.js",
      "runtime/check-api.js",
      "runtime/layer-client.js",
      "runtime/media.js",
      "runtime/vendor-bridge.js",
      "runtime/widget-api.js",
    ]);
    assert.deepEqual(Object.keys(record.inputs), Object.keys(sources).sort());
    assert.deepEqual(record.replaces, [
      "leaf.js",
      "runtime/annotation-overlay/check-api.js",
      "runtime/annotation-overlay/index.js",
      "runtime/check-api.js",
      "runtime/framework.js",
      "runtime/framework/render.js",
      "runtime/layer-client.js",
      "runtime/media.js",
      "runtime/state.js",
      "runtime/vendor-bridge.js",
      "runtime/widget-api.js",
      "vendor/signals-core.js",
    ]);
    assert.match(kernel.get("leaf.js").toString(), /import\("\/widgets\/custom.js"\)/);
    const javascript = [...kernel]
      .filter(([path]) => path.endsWith(".js"))
      .map(([, bytes]) => bytes)
      .join("\n");
    // The framework shares the runtime's one state instance and the page's one Lit.
    assert.equal(javascript.split("clicks: 0").length - 1, 1);
    assert.match(javascript, /from "\/vendor\/lit\.js"/);
    // A lazily imported kernel module is a chunk, and its vendor import stays native.
    assert.match(javascript, /import\("\/vendor\/example\.js"\)/);
    assert.doesNotMatch(javascript, /from "[^"]*signals-core|bundle-[A-Z0-9]{8}/);
    // A historical developer arm may predate the optional diagnostic entry.
    await rm(join(layer, "runtime/annotation-overlay/check-api.js"));
    const historical = join(temporary, "historical");
    await vendor(layer, await kernelOutputs(layer), historical);
    await writeFile(join(historical, "package.json"), '{"type":"module"}');
    const prior = await import(pathToFileURL(join(historical, "leaf.js")));
    assert.equal(prior.state.annotations, false);
  } finally {
    await rm(temporary, { recursive: true });
  }
});
