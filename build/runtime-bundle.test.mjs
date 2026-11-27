/** The kernel shares one state instance with native package modules. */
import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

import { kernelOutputs, runtimeEntries } from "./runtime-bundle.mjs";

// The entries the fixture below writes a source of its own for, to follow state
// through them.
const traced = new Set([
  "leaf.js",
  "runtime/transport/layer-client.js",
  "runtime/records/media.js",
  "runtime/widget-api.js",
  "runtime/portable-api.js",
  "runtime/check-api.js",
]);
// Every other entry of the kernel's, such as the library's modules. A stub stands for
// each one the bundler lists, so a module that joins the public ones changes nothing
// here.
const library = runtimeEntries.filter((path) => !traced.has(path));
const besideLibrary = (paths) => paths.filter((path) => !library.includes(path));

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
      'export { state } from "./runtime/state.js"; export const annotations = () => import("./runtime/annotations/annotation-overlay/index.js"); export const widget = () => import("./widgets/custom.js");',
    "runtime/state.js": "export const state = { clicks: 0, annotations: false };",
    "runtime/vendor-bridge.js": 'export { state } from "./state.js";',
    "runtime/widget-api.js": 'export { state } from "./state.js";',
    "runtime/portable-api.js":
      'export const clock = () => import("./base/document-inputs.js"); export { state } from "./state.js";',
    "runtime/base/document-inputs.js": "(() => {})();",
    "runtime/check-api.js": 'export { state } from "./state.js";',
    "runtime/annotations/annotation-overlay/check-api.js":
      'export { state } from "../../state.js";',
    "runtime/records/media.js":
      'export { state } from "../state.js"; export { rendered } from "./framework.js";',
    "runtime/transport/layer-client.js": 'export { state } from "../state.js";',
    "runtime/annotations/annotation-overlay/index.js":
      'import { state } from "../../state.js"; export { state }; state.annotations = true; export const vendor = () => import("../../../vendor/example.js");',
    "runtime/bootstrap.js": "(() => { window.boot = true; })();",
    "widgets/custom.js":
      'import { state } from "/runtime/widget-api.js"; state.clicks += 1;',
    "vendor/example.js": 'export { state } from "/runtime/vendor-bridge.js";',
    "vendor/lit.js": "export const html = (strings) => strings.join('');\n",
    "vendor/signals-core.js": "export const signal = (value) => ({ value });\n",
    "runtime/records/framework.js":
      'export { rendered } from "./framework/render.js";\n',
    "runtime/records/framework/render.js":
      'import { html } from "/vendor/lit.js";\nimport { signal } from "/vendor/signals-core.js";\nimport { state } from "../../state.js";\n\nexport const rendered = () => html([signal(state).value]);\n',
    ...Object.fromEntries(
      library.map((path) => [path, `export const home = ${JSON.stringify(path)};\n`]),
    ),
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
    assert.equal(
      await readFile(join(output, "runtime/base/document-inputs.js"), "utf8"),
      sources["runtime/base/document-inputs.js"],
    );
    await writeFile(join(output, "package.json"), '{"type":"module"}');

    const leaf = await import(pathToFileURL(join(output, "leaf.js")).href);
    const api = await import(pathToFileURL(join(output, "runtime/widget-api.js")).href);
    const checks = await import(
      pathToFileURL(join(output, "runtime/check-api.js")).href
    );
    const portable = await import(
      pathToFileURL(join(output, "runtime/portable-api.js")).href
    );
    const overlayChecks = await import(
      pathToFileURL(join(output, "runtime/annotations/annotation-overlay/check-api.js"))
        .href
    );
    assert.equal(leaf.state.annotations, false);
    assert.equal(checks.state, leaf.state);
    assert.equal(portable.state, leaf.state);
    assert.equal(overlayChecks.state, leaf.state);
    const annotations = await leaf.annotations();
    assert.equal(leaf.state.annotations, true);
    const bridge = await import(
      pathToFileURL(join(output, "runtime/vendor-bridge.js")).href
    );
    assert.equal(api.state, leaf.state);
    assert.equal(bridge.state, leaf.state);
    assert.equal(annotations.state, leaf.state);
    api.state.clicks += 1;
    assert.equal(annotations.state.clicks, 1);

    // The kernel is runtime modules and chunks named after their modules, but for
    // the one holding what the portable helpers reach, the shared state here; it
    // absorbs the framework and its signals and leaves widgets, upstream vendor
    // modules, and the classic scripts nothing imports native. Each library module
    // keeps its own path, for the package that imports it there.
    for (const path of library) assert(kernel.has(path), path);
    assert.deepEqual(besideLibrary([...kernel.keys()].sort()), [
      "kernel.json",
      "leaf.js",
      "runtime/annotations/annotation-overlay/check-api.js",
      "runtime/bundle-annotation-overlay.js",
      "runtime/bundle-portable.js",
      "runtime/check-api.js",
      "runtime/portable-api.js",
      "runtime/records/media.js",
      "runtime/transport/layer-client.js",
      "runtime/vendor-bridge.js",
      "runtime/widget-api.js",
    ]);
    assert.deepEqual(Object.keys(record.inputs), Object.keys(sources).sort());
    assert.deepEqual(besideLibrary(record.replaces), [
      "leaf.js",
      "runtime/annotations/annotation-overlay/check-api.js",
      "runtime/annotations/annotation-overlay/index.js",
      "runtime/check-api.js",
      "runtime/portable-api.js",
      "runtime/records/framework.js",
      "runtime/records/framework/render.js",
      "runtime/records/media.js",
      "runtime/state.js",
      "runtime/transport/layer-client.js",
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
  } finally {
    await rm(temporary, { recursive: true });
  }
});
