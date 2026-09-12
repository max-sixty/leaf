import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { buildOutputs, checkModule, checkOutputs } from "./build.mjs";
import { createApplicationPublisher } from "./snapshot.ts";

const outputs = await buildOutputs();
const outputRoot = "skills/leaf/assets/vendor";

test("locked source reproduces the complete committed output", async () => {
  const rebuilt = await buildOutputs();
  assert.deepEqual(rebuilt, outputs);
  await checkOutputs(outputs);
  const manifest = JSON.parse(
    outputs.get(`${outputRoot}/browser-runtime.manifest.json`),
  );
  assert.deepEqual(manifest.exports, [
    "LitElement",
    "createApplicationPublisher",
    "createSemanticApplication",
    "html",
  ]);
  assert.deepEqual(manifest.externalizedModules, []);
  const map = JSON.parse(outputs.get(`${outputRoot}/browser-runtime.js.map`));
  assert.ok(map.sources.some((name) => name.endsWith("scripts/browser/snapshot.ts")));
  assert.equal(map.sources.length, map.sourcesContent.length);
  assert.ok(map.sources.every((name) => !path.isAbsolute(name)));
});

test("checking stale output refuses it without changing any bytes", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-browser-build-"));
  context.after(() => rm(scratch, { recursive: true }));
  await mkdir(path.join(scratch, outputRoot), { recursive: true });
  for (const [name, bytes] of outputs) await writeFile(path.join(scratch, name), bytes);
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

test("the bundle gate rejects unresolved code and runtime compilation", () => {
  for (const source of [
    'import { html } from "lit";',
    'export { html } from "https://cdn.example/lit.js";',
    'import("./late.js");',
    'eval("globalThis.changed = true");',
    'new Function("return 1")();',
    'require("lit");',
  ]) {
    assert.throws(() => checkModule(source), /self-contained ESM/, source);
  }
  checkModule('export const words = "eval and import are ordinary prose here";');
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
