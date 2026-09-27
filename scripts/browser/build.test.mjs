import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { buildOutputs, checkOutputs } from "./build.mjs";
import { bundledPackages, checkModule } from "./shipped.mjs";
import { createApplicationPublisher } from "./snapshot.ts";

const outputs = await buildOutputs();
const outputRoot = "skills/leaf/assets/vendor";
const diagnosticsRoot = "scripts/browser/generated";

test("locked source reproduces the complete committed output", async () => {
  const rebuilt = await buildOutputs();
  assert.deepEqual(rebuilt, outputs);
  await checkOutputs(outputs);
  const manifest = JSON.parse(
    outputs.get(`${diagnosticsRoot}/browser-runtime.manifest.json`),
  );
  assert.deepEqual(manifest.exports, [
    "LitElement",
    "PRESENTATION_HELD",
    "createPresentationCoordinator",
    "createPresentationSchedule",
    "createSemanticApplication",
    "describeFailure",
    "html",
    "nothing",
    "render",
    "repeat",
  ]);
  // The page's one Lit: the framework imports it rather than carrying a copy.
  assert.match(
    outputs.get(`${outputRoot}/browser-runtime.js`).toString(),
    /^import\{[^}]*\}from"\.\/lit\.js"/,
  );
  assert.ok(
    !outputs.get(`${outputRoot}/browser-runtime.js`).includes("litHtmlVersions"),
  );
  for (const name of ["LitElement", "html", "classMap", "property", "staticHtml"])
    assert.ok(manifest.litExports.includes(name), name);
  assert.ok(outputs.has(`${outputRoot}/browser-runtime.LICENSES.txt`));
  assert.ok(
    !outputs.get(`${outputRoot}/browser-runtime.js`).includes("sourceMappingURL"),
  );
  assert.ok(!outputs.has(`${outputRoot}/browser-runtime.js.map`));
  assert.ok(!outputs.has(`${outputRoot}/browser-runtime.manifest.json`));
  const map = JSON.parse(outputs.get(`${diagnosticsRoot}/browser-runtime.js.map`));
  assert.ok(map.sources.includes("../snapshot.ts"));
  assert.equal(map.sources.length, map.sourcesContent.length);
  assert.ok(map.sources.every((name) => !path.isAbsolute(name)));
});

test("checking stale output refuses it without changing any bytes", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-browser-build-"));
  context.after(() => rm(scratch, { recursive: true }));
  for (const [name, bytes] of outputs) {
    const destination = path.join(scratch, name);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, bytes);
  }
  await checkOutputs(outputs, scratch);
  const module = path.join(scratch, outputRoot, "browser-runtime.js");
  const stale = Buffer.from("export const stale = true;\n");
  await writeFile(module, stale);
  await assert.rejects(
    checkOutputs(outputs, scratch),
    /Stale browser output.*\n.*browser-runtime\.js/s,
  );
  assert.deepEqual(await readFile(module), stale);
  await rm(module);
  await assert.rejects(checkOutputs(outputs, scratch), /browser-runtime\.js/);
});

test("the bundle gate reads the parsed module, not its text", () => {
  for (const [source, reason] of [
    ['import { html } from "lit";', 'imports "lit", not a local path'],
    ['export { html } from "https://cdn.example/lit.js";', "not a local path"],
    ['export * from "//cdn.example/lit.js";', "not a local path"],
    ['import("./late.js");', "import() loads a module at run time"],
    ['eval("globalThis.changed = true");', "calls eval"],
    ['(0, eval)("1");', "calls eval"],
    ['globalThis["eval"]("1");', "calls eval"],
    ['new Function("return 1")();', "calls Function"],
    ['window.Function("return 1")();', "calls Function"],
    ['require("lit");', "calls require"],
    ['setTimeout("document.body.dataset.ready=1", 0);', "passes setTimeout a string"],
    ["window.setInterval(`tick(${a})`, 9);", "passes setInterval a string"],
    ['setTimeout("tick(" + a + ")", 9);', "passes setTimeout a string"],
  ]) {
    assert.throws(
      () => checkModule(`const a = 1;\n${source}`, "x.js"),
      (error) =>
        error.message.startsWith("x.js:2: ") &&
        error.message.includes(reason) &&
        error.message.endsWith("which the page CSP forbids"),
      source,
    );
  }
  checkModule('import { html } from "./lit.js";');
  checkModule("setTimeout(() => tick(), 9); setInterval(tick, 9 + 1);");
  checkModule('import { html } from "/vendor/lit.js"; export * from "../a.js";');
  // Pierre's TextMate grammars carry both as data.
  checkModule('export const grammar = { begin: "import\\\\(", end: "eval(x)" };');
});

test("notices name the packages whose code reached an output", () => {
  const metafile = {
    inputs: { "node_modules/a/x.js": {}, "node_modules/@s/b/y.js": {} },
    outputs: {
      "out.js": {
        inputs: {
          "node_modules/a/x.js": { bytesInOutput: 0 },
          "node_modules/@s/b/node_modules/c/z.js": { bytesInOutput: 3 },
          "node_modules/@s/b/y.js": { bytesInOutput: 5 },
          "entry.mjs": { bytesInOutput: 9 },
        },
      },
      "out.js.map": { inputs: {} },
    },
  };
  assert.deepEqual(bundledPackages(metafile, "/w"), [
    "/w/node_modules/@s/b",
    "/w/node_modules/@s/b/node_modules/c",
  ]);
});

test("publisher replaces one immutable reading before subscribers run", () => {
  const activity = { state: "waiting" };
  const initial = {
    document: { revision: 1 },
    authoritative: { activity, through: 0 },
    unresolved: [],
    effective: { decision: "open" },
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  const decision = publisher.select((state) => state.effective.decision);
  const delivery = publisher.select((state) => state.unresolved.length);
  const seen = [];
  const dispose = decision.subscribe((value) =>
    seen.push([value, delivery.read(), publisher.read().semanticEpoch]),
  );
  const pending = {
    ...initial,
    unresolved: [{ attempt: "choose-a" }],
    effective: { decision: "a" },
    semanticEpoch: 1,
  };

  assert.equal(publisher.publish(pending), pending);
  assert.deepEqual(seen, [
    ["open", 0, 0],
    ["a", 1, 1],
  ]);
  assert.equal(publisher.read().authoritative.activity, activity);
  assert.throws(() => {
    publisher.read().unresolved[0].attempt = "corrupt";
  }, TypeError);
  assert.throws(() => {
    publisher.read().effective.decision = "corrupt";
  }, TypeError);
  publisher.publish({
    ...pending,
    unresolved: [],
    authoritative: { activity, through: 1 },
  });
  assert.equal(seen.length, 2);
  assert.equal(delivery.read(), 0);
  dispose();
  publisher.publish({ ...initial, semanticEpoch: 2 });
  assert.equal(seen.length, 2);
  assert.equal(decision.read(), "open");
});
