import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { build } from "esbuild";
import { adapt, seam } from "../vendor.mjs";
import { buildOutputs, checkOutputs } from "./build.mjs";
import { bundledPackages, checkModule } from "./shipped.mjs";
import { createApplicationPublisher, share } from "./snapshot.ts";

const outputs = await buildOutputs();
const root = fileURLToPath(new URL("../../", import.meta.url));
const vendor = "skills/leaf/assets/vendor";
const read = (name) => outputs.get(`${vendor}/${name}`).toString();
const exportsOf = (code) =>
  parse(code, { ecmaVersion: "latest", sourceType: "module" })
    .body.filter((node) => node.type === "ExportNamedDeclaration")
    .flatMap((node) => node.specifiers.map((specifier) => specifier.exported.name))
    .sort();

test("locked source reproduces the complete committed output", async () => {
  const rebuilt = await buildOutputs();
  assert.deepEqual(rebuilt, outputs);
  await checkOutputs(outputs);
  assert.deepEqual(exportsOf(read("browser-runtime.js")), [
    "AsyncDirective",
    "Directive",
    "LitElement",
    "PRESENTATION_HELD",
    "PartType",
    "classMap",
    "collectReads",
    "createPresentationCoordinator",
    "createPresentationSchedule",
    "createRef",
    "createSemanticApplication",
    "describeFailure",
    "directive",
    "effect",
    "guard",
    "html",
    "keyed",
    "live",
    "noChange",
    "nothing",
    "ref",
    "render",
    "repeat",
    "share",
    "signal",
    "styleMap",
    "unsafeHTML",
  ]);
  const lit = exportsOf(read("lit.js"));
  for (const name of ["LitElement", "html", "classMap", "property", "staticHtml"])
    assert.ok(lit.includes(name), name);
  const notices = read("browser-runtime.LICENSES.txt");
  for (const name of ["lit-html", "@preact/signals-core"])
    assert.ok(notices.includes(`===== ${name} `), name);
});

test("each source module compiles to one module that keeps its lines", async () => {
  const modules = [...outputs.keys()].filter((name) =>
    name.startsWith(`${vendor}/browser-runtime/`),
  );
  for (const name of ["application", "presentation", "snapshot"]) {
    const source = (
      await readFile(new URL(`./${name}.ts`, import.meta.url), "utf8")
    ).split("\n");
    const compiled = read(`browser-runtime/${name}.js`).split("\n");
    // One trailer line names the source; every other line is the source's.
    assert.equal(compiled.length, source.length + 1, name);
    // Each line is its source line with types blanked; only import paths move.
    for (const [index, line] of compiled.slice(0, -2).entries())
      if (!/\bfrom "/.test(line))
        assert.ok(
          line.length <= source[index].length &&
            [...line].every((char, at) => char === source[index][at] || char === " "),
          `${name}.ts:${index + 1}`,
        );
    assert.ok(modules.includes(`${vendor}/browser-runtime/${name}.js`));
  }
  // Runtime modules stay native, so the page holds one instance of each.
  assert.match(
    read("browser-runtime/application.js"),
    /^} from "\.\.\/\.\.\/runtime\/thread\/model\.js";$/m,
  );
  // The page's one Lit: the framework imports it rather than carrying a copy.
  assert.match(read("browser-runtime.js"), /^export \{[^}]*\} from "\.\/lit\.js";$/m);
  assert.match(
    read("browser-runtime/snapshot.js"),
    /^import \{ computed, signal \} from "\.\/signals-core\.js";$/m,
  );
  for (const name of modules.filter((name) => !name.endsWith("signals-core.js")))
    assert.ok(!outputs.get(name).includes("litHtmlVersions"), name);
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
  const module = path.join(scratch, vendor, "browser-runtime.js");
  const stale = Buffer.from("export const stale = true;\n");
  await writeFile(module, stale);
  await assert.rejects(
    checkOutputs(outputs, scratch),
    /Stale browser output.*\n.*browser-runtime\.js/s,
  );
  assert.deepEqual(await readFile(module), stale);
  await rm(module);
  await assert.rejects(checkOutputs(outputs, scratch), /browser-runtime\.js/);
  await writeFile(module, outputs.get(`${vendor}/browser-runtime.js`));
  // A module whose source is gone is stale too.
  await writeFile(path.join(scratch, vendor, "browser-runtime", "removed.js"), "");
  await assert.rejects(checkOutputs(outputs, scratch), /browser-runtime\/removed\.js/);
  await rm(path.join(scratch, vendor, "browser-runtime", "removed.js"));
  // So is any file in a package's vendor directory that no build writes.
  const chunk = "skills/leaf/packages/diagram/vendor/chunk-removed.js";
  await writeFile(path.join(scratch, chunk), "");
  await assert.rejects(checkOutputs(outputs, scratch), new RegExp(chunk));
});

test("an upstream adaptation fails the build once its seam or its module moves", async () => {
  const bundle = (adaptations) =>
    build({
      stdin: {
        contents: 'export { diffArrays } from "diff/lib/diff/array.js";',
        resolveDir: root,
      },
      absWorkingDir: root,
      bundle: true,
      format: "esm",
      write: false,
      logLevel: "silent",
      plugins: [adapt(adaptations)],
    });
  const file = /diff[/\\]libesm[/\\]diff[/\\]array\.js$/;
  const edited = await bundle([
    { file, edit: (source) => seam(source, "arrayDiff.diff(", "arrayDiff.leaf(", "x") },
  ]);
  assert.match(edited.outputFiles[0].text, /arrayDiff\.leaf\(/);
  await assert.rejects(
    bundle([{ file, edit: (source) => seam(source, "class Missing", "", "Array") }]),
    /Array seam changed: class Missing/,
  );
  await assert.rejects(
    bundle([
      { file, edit: (source) => source },
      { file: /moved\.js$/, edit: (s) => s },
    ]),
    /no module matches adaptation \/moved\\\.js\$\//,
  );
});

test("the bundle gate reads the parsed module, not its text", () => {
  for (const [source, reason] of [
    ['import { html } from "lit";', 'imports "lit", not a local path'],
    ['export { html } from "https://cdn.example/lit.js";', "not a local path"],
    ['export * from "//cdn.example/lit.js";', "not a local path"],
    ['import("./late.js");', "import() loads a module at run time"],
    ['require("lit");', "require() loads a module at run time"],
  ]) {
    assert.throws(
      () => checkModule(`const a = 1;\n${source}`, "x.js"),
      (error) =>
        error.message.startsWith("x.js:2: ") &&
        error.message.includes(reason) &&
        error.message.endsWith("which an export cannot load"),
      source,
    );
  }
  checkModule('import { html } from "./lit.js";');
  checkModule('new Function("return 1")();');
  checkModule('import { html } from "/vendor/lit.js"; export * from "../a.js";');
  // Pierre's TextMate grammars carry it as data.
  checkModule('export const grammar = { begin: "import\\\\(", end: "require(x)" };');
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

test("publisher shares unchanged subtrees, so a selection hears only its own part move", () => {
  const initial = {
    document: { revision: 1 },
    authoritative: {},
    unresolved: [],
    effective: {
      thread: { all: [{ id: "t1", words: ["hello"] }] },
      widgets: new Map([["board", { state: { column: "todo" } }]]),
    },
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  const thread = publisher.select((root) => root.effective.thread);
  const pair = publisher.select((root) => [
    root.effective.thread.all[0],
    root.document.revision,
  ]);
  const heard = [];
  thread.subscribe((value) => heard.push(["thread", value]));
  pair.subscribe((value) => heard.push(["pair", value]));
  const standing = thread.read();
  const standingPair = pair.read();
  publisher.publish({
    ...initial,
    effective: {
      thread: { all: [{ id: "t1", words: ["hello"] }] },
      widgets: new Map([["board", { state: { column: "done" } }]]),
    },
  });
  assert.equal(thread.read(), standing);
  assert.equal(pair.read(), standingPair);
  assert.equal(heard.length, 2);
  publisher.publish({
    ...initial,
    effective: {
      thread: { all: [{ id: "t1", words: ["hello", "again"] }] },
      widgets: new Map([["board", { state: { column: "done" } }]]),
    },
  });
  assert.notEqual(thread.read(), standing);
  assert.deepEqual(
    heard.slice(2).map(([name]) => name),
    ["thread", "pair"],
  );
});

test("sharing keeps a JSON field named __proto__ an own field", () => {
  const prior = JSON.parse('{"kept": {"a": 1}, "__proto__": {"x": 1}}');
  const next = JSON.parse('{"kept": {"a": 1}, "__proto__": {"x": 2}}');
  const shared = share(prior, next);
  assert.equal(Object.getPrototypeOf(shared), Object.prototype);
  assert.ok(Object.hasOwn(shared, "__proto__"));
  assert.deepEqual(Object.getOwnPropertyDescriptor(shared, "__proto__").value, {
    x: 2,
  });
  assert.equal(shared.kept, prior.kept);
});

test("publisher secures shallow-frozen inputs and complete selected collections", () => {
  const key = { id: "thread" };
  const collection = Object.freeze(new Map([[key, { words: ["kept"] }]]));
  const document = Object.freeze({ collection });
  const publisher = createApplicationPublisher({
    document,
    authoritative: {},
    unresolved: [],
    effective: {},
    semanticEpoch: 0,
  });
  const selected = publisher
    .select(() =>
      Object.freeze({
        nested: { count: 1 },
        members: Object.freeze(new Set([{ id: "message" }])),
      }),
    )
    .read();
  assert.throws(() => {
    selected.nested.count = 2;
  }, TypeError);
  assert.throws(() => {
    selected.members.add("extra");
  }, TypeError);
  assert.throws(() => {
    [...selected.members][0].id = "changed";
  }, TypeError);
  const reading = publisher.read();
  assert.throws(() => {
    [...reading.document.collection.keys()][0].id = "changed";
  }, TypeError);
  assert.throws(() => {
    reading.document.collection.get(key).words.push("changed");
  }, TypeError);
  assert.throws(() => {
    reading.document.collection.set("extra", {});
  }, TypeError);
  collection.set("outside", { words: [] });
  assert.equal(reading.document.collection.has("outside"), false);
  publisher.publish({ ...reading, document, semanticEpoch: 1 });
  assert.equal(publisher.read().document.collection.has("outside"), true);
});
