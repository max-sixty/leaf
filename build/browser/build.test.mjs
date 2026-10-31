import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { parse } from "acorn";
import { build } from "esbuild";
import { adapt, seam } from "../vendor.mjs";
import {
  buildOutputs,
  checkOutputs,
  checkRuntimeModules,
  compilerPaths,
} from "./build.mjs";
import { bundledPackages, checkModule } from "./shipped.mjs";

const outputs = await buildOutputs();
const root = fileURLToPath(new URL("../../", import.meta.url));
const vendor = "browser/vendor";
const read = (name) => outputs.get(`${vendor}/${name}`).toString();
const exportsOf = (code) =>
  parse(code, { ecmaVersion: "latest", sourceType: "module" })
    .body.filter((node) => node.type === "ExportNamedDeclaration")
    .flatMap((node) =>
      node.specifiers.map((specifier) =>
        specifier.exported.type === "Identifier"
          ? specifier.exported.name
          : specifier.exported.value,
      ),
    )
    .sort();

test("compiler paths discover package modules and type the framework's bundles", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-compiler-paths-"));
  context.after(() => rm(scratch, { recursive: true }));
  const put = async (name, text) => {
    const destination = path.join(scratch, name);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, text);
  };
  const config = JSON.parse(
    await readFile(
      new URL("../../browser/types/tsconfig.json", import.meta.url),
      "utf8",
    ),
  );
  config.compilerOptions.types = [];
  config.compilerOptions.noUncheckedSideEffectImports = true;
  config.include = ["imports.ts"];
  await put("browser/types/tsconfig.json", JSON.stringify(config));
  await put(
    "browser/types/signals-core.d.ts",
    "export declare const count: (value: number) => number;\n",
  );
  await put("browser/vendor/signals-core.js", "export const count = 1;\n");
  await put("packages/playground/vendor/playground-support.js", "void 0;\n");
  await put("packages/playwright/widgets/lf-trace.js", "export const trace = 1;\n");
  await put(
    "browser/types/imports.ts",
    `
import { count } from "/vendor/signals-core.js";
import "/vendor/playground-support.js";
import { trace } from "/widgets/lf-trace.js";
import { future } from "/vendor/lf-future.js";
import { widget } from "/widgets/lf-future.js";
count(trace + future + widget);
// @ts-expect-error The bundle reads as its declaration, not as the minified module.
count("wrong");
`,
  );
  const check = () =>
    spawnSync(
      process.execPath,
      [
        path.join(root, "node_modules/typescript/bin/tsc"),
        "--project",
        path.join(scratch, "browser/types/tsconfig.json"),
        "--pretty",
        "false",
      ],
      { encoding: "utf8" },
    );
  await put("browser/types/tsconfig.paths.json", await compilerPaths(scratch));
  const missing = check();
  assert.equal(missing.status, 1, missing.stdout + missing.stderr);
  assert.match(missing.stdout, /Cannot find module '\/vendor\/lf-future.js'/);
  assert.match(missing.stdout, /Cannot find module '\/widgets\/lf-future.js'/);
  assert.doesNotMatch(
    missing.stdout,
    /Cannot find module '\/(?:vendor\/playground-support|widgets\/lf-trace)/,
  );

  await put("packages/future/vendor/lf-future.js", "export const future = 2;\n");
  await put("packages/future/widgets/lf-future.js", "export const widget = 3;\n");
  await put("browser/types/tsconfig.paths.json", await compilerPaths(scratch));
  const discovered = check();
  assert.equal(discovered.status, 0, discovered.stdout + discovered.stderr);
});

test("framework modules require their checking pragma", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-runtime-pragma-"));
  context.after(() => rm(scratch, { recursive: true }));
  const runtime = path.join(scratch, "browser/runtime");
  await mkdir(path.join(runtime, "framework"), { recursive: true });
  const file = path.join(runtime, "framework/unimported.js");
  await writeFile(file, "export const value = 1;\n");
  await assert.rejects(checkRuntimeModules(scratch), {
    message:
      "Start each framework module with `// @ts-check`, so the strict program checks it:\nbrowser/runtime/framework/unimported.js",
  });
  await writeFile(file, "// @ts-check\nexport const value = 1;\n");
  await checkRuntimeModules(scratch);
});

test("runtime TypeScript is refused by build and check, with declarations allowed", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-runtime-source-"));
  context.after(() => rm(scratch, { recursive: true }));
  const runtime = path.join(scratch, "browser/runtime/nested");
  await mkdir(runtime, { recursive: true });
  await writeFile(path.join(runtime, "types.d.ts"), "export type Value = number;\n");
  await checkRuntimeModules(scratch);
  await writeFile(path.join(runtime, "unimported.ts"), "export const value = 1;\n");
  await assert.rejects(checkRuntimeModules(scratch), {
    message:
      "Runtime modules are JavaScript with JSDoc so an edit reaches pages and tests without a build (#4112):\nbrowser/runtime/nested/unimported.ts",
  });
});

test("locked source reproduces the complete committed output", async () => {
  const rebuilt = await buildOutputs();
  assert.deepEqual(rebuilt, outputs);
  await checkOutputs(outputs);
  const lit = exportsOf(read("lit.js"));
  for (const name of ["LitElement", "html", "classMap", "property", "staticHtml"])
    assert.ok(lit.includes(name), name);
  for (const [bundle, name] of [
    ["lit", "lit-html"],
    ["signals-core", "@preact/signals-core"],
  ])
    assert.ok(read(`${bundle}.LICENSES.txt`).includes(`===== ${name} `), name);
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
  const paths = "browser/types/tsconfig.paths.json";
  await writeFile(path.join(scratch, paths), "{}\n");
  await assert.rejects(checkOutputs(outputs, scratch), /tsconfig\.paths\.json/);
  assert.equal(await readFile(path.join(scratch, paths), "utf8"), "{}\n");
  await writeFile(path.join(scratch, paths), outputs.get(paths));
  const module = path.join(scratch, vendor, "signals-core.js");
  const stale = Buffer.from("export const stale = true;\n");
  await writeFile(module, stale);
  await assert.rejects(
    checkOutputs(outputs, scratch),
    /Stale browser output.*\n.*signals-core\.js/s,
  );
  assert.deepEqual(await readFile(module), stale);
  await rm(module);
  await assert.rejects(checkOutputs(outputs, scratch), /signals-core\.js/);
  await writeFile(module, outputs.get(`${vendor}/signals-core.js`));
  // A module whose source is gone is stale too.
  await writeFile(path.join(scratch, vendor, "removed.js"), "");
  await assert.rejects(checkOutputs(outputs, scratch), /vendor\/removed\.js/);
  await rm(path.join(scratch, vendor, "removed.js"));
  // So is any file in a package's vendor directory that no build writes.
  const chunk = "packages/diagram/vendor/chunk-removed.js";
  await writeFile(path.join(scratch, chunk), "");
  await assert.rejects(checkOutputs(outputs, scratch), new RegExp(chunk));
  await rm(path.join(scratch, chunk));
  // A kernel left behind by a merge names the command that rebuilds it.
  const kernel = path.join(scratch, "dist/kernel/leaf.js");
  await writeFile(kernel, "<<<<<<< ours\n");
  await assert.rejects(
    checkOutputs(outputs, scratch),
    (error) =>
      error instanceof Error &&
      error.message.includes(
        "pnpm install --frozen-lockfile && pnpm run build:browser",
      ) &&
      error.message.endsWith("\ndist/kernel/leaf.js"),
  );
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
        error instanceof Error &&
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

test("Trees search hides every nonmatch and restores an empty query", async () => {
  // Exercise the actual shipped dependency, including its build adaptations.
  const bundle = outputs.get("packages/file-tree/vendor/pierre-trees.esm.js");
  const { FileTree } = await import(
    `data:text/javascript;base64,${bundle.toString("base64")}`
  );
  const tree = new FileTree({
    paths: ["README.md", "src/main.py"],
    initialExpansion: "open",
    search: true,
  });
  try {
    const visible = () =>
      tree.getVisibleRows(0, tree.getVisibleCount() - 1).map(({ path }) => path);
    const unfiltered = visible();
    tree.setSearch("main");
    assert.deepEqual(visible(), ["src/", "src/main.py"]);
    tree.setSearch("not-a-file");
    assert.deepEqual(tree.getSearchMatchingPaths(), []);
    assert.deepEqual(visible(), []);
    tree.setSearch("");
    assert.deepEqual(visible(), unfiltered);
  } finally {
    tree.cleanUp();
  }
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
