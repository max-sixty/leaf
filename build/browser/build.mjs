#!/usr/bin/env node
/**
 * Build Leaf's committed browser outputs from locked contributor dependencies.
 * Invoke through pnpm run build:browser or check:browser; pnpm verifies that the
 * installed dependencies match the manifest and lock before either script runs.
 *
 * Run with --check to compare a fresh, typechecked build with committed bytes
 * without writing them. This module type-checks the runtime, builds the framework's
 * third-party packages, and writes and checks every other committed Node-built output
 * beside them: the third-party
 * stylesheets (`build/styles.mjs`), the page protocol's types, the event records and
 * the served state (`contract-types.mjs`), and the baseline its schemas are held to
 * (`protocol.mjs`), the third-party bundles and the runtime's table of their grammars
 * (`build/vendor.mjs`), and last the kernel compiled from all of them
 * (`build/runtime-bundle.mjs`). The kernel's directory, the layer's `vendor/` and each
 * package's hold nothing else, so a file there that no build writes is stale. Leaf
 * installation, vendoring, activation, and
 * export never invoke this tool.
 * The compiler's layer paths are generated into `tsconfig.paths.json` from the
 * package directories, so its CLI and editors resolve the same installed modules.
 *
 * The framework (`runtime/framework.js` and the modules behind it) is written as
 * JavaScript the type check reads, so a page serves its source as it does every other
 * runtime module. Its third-party packages are minified builds from the lock and the
 * adaptations below. Runtime and package modules load one ordinary Lit module
 * (`build/lit.mjs`). Signals are the framework's own: the kernel compiles them in
 * with it (`runtime-bundle.mjs`). `shipped.mjs` decides whether each output's imports
 * resolve on every page and writes notices for the packages that reached
 * them, as it does for every vendored bundle.
 */
import { readFileSync } from "node:fs";
import { cp, mkdtemp, readFile, readdir, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { build } from "../esbuild.mjs";
import { contractTypes, protocolSchemas } from "./contract-types.mjs";
import { baselineSchemas, protocolBreaks } from "./protocol.mjs";
import { litNamespace, litPath } from "../lit.mjs";
import { styleOutputs } from "../styles.mjs";
import { kernelOutputs } from "../runtime-bundle.mjs";
import { adapt, seam, vendorOutputs } from "../vendor.mjs";
import { bundledPackages, checkModule, licenseNotices } from "./shipped.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const assets = "browser";
/** The committed kernel, which installs serve while it matches the tree's modules. */
const kernelDirectory = "dist/kernel";
/** The type check's configurations and the declarations of the bundles it reads. */
const typeRoot = "browser/types";
const compilerPathsFile = `${typeRoot}/tsconfig.paths.json`;
const litTypesFile = `${typeRoot}/lit.d.ts`;
const packageRoot = "packages";
/** The layer path of the framework's signals, which the kernel compiles in. */
export const signalsPath = "vendor/signals-core.js";

/** Package directories in deterministic order, shared by paths and build ownership. */
async function packageDirectories(directory) {
  return (
    await readdir(path.join(directory, packageRoot), { withFileTypes: true }).catch(
      missing,
    )
  )
    .filter((entry) => entry.isDirectory())
    .map(({ name }) => `${packageRoot}/${name}`)
    .sort();
}

/** Compiler paths for the rooted URLs the layer serves, with the framework's bundles
 * typed from the packages they bundle. */
export async function compilerPaths(directory = root) {
  const roots = [assets, ...(await packageDirectories(directory))];
  const paths = {
    [`/${litPath}`]: ["./lit.d.ts"],
    [`/${signalsPath}`]: ["./signals-core.d.ts"],
    ...Object.fromEntries(
      ["vendor", "widgets"].map((kind) => [
        `/${kind}/*`,
        roots.map((base) => path.posix.relative(typeRoot, `${base}/${kind}/*`)),
      ]),
    ),
    "/runtime/*": [path.posix.relative(typeRoot, `${assets}/runtime/*`)],
    "/checks/*": ["../../src/leaf/render-checks/*"],
  };
  return Buffer.from(`${JSON.stringify({ compilerOptions: { paths } }, null, 2)}\n`);
}

/** The types of `/vendor/lit.js`, whose minified build carries none: the namespace
 * it bundles (`build/lit.mjs`), read from Lit's own declarations. */
async function litTypes() {
  return Buffer.from(
    `/* @noformat Generated from Lit's package exports by build/browser/build.mjs. */\n${await litNamespace()}\n`,
  );
}
/**
 * Build the shared Lit implementation, adapting the locked published modules in memory.
 *
 * Backport lit/lit#5218 while 3.3.0 avoids the repeat marker leak (#5298). Route
 * keyed and child-part insertions through the mover a Leaf page installs on its root
 * (`lfMove`, installed by `runtime/dom-move.js`, which keeps
 * the user's place and native state across the move). A document Leaf did not compose
 * has no mover, and Lit inserts as it always does, so this Lit loads in any document.
 *
 * `package.json` holds `lit-html` at 3.3.0 for that leak: from 3.3.1 `repeat` leaves a
 * comment behind for each item it removes, so a list the chrome redraws grows for as
 * long as the page is open. Lift the pin to a release that carries lit/lit#5299; the
 * closed-surface journey of `test_page_fixture_renders` fails while the leak remains.
 */
async function litModule() {
  const contents = await litNamespace();
  const move =
    "const leafMove = (parent, node, before) => { const move = window.lfMove; return move ? move(parent, node, before) : parent.insertBefore(node, before); };\n";
  return [
    {
      name: "leaf-lit",
      setup(build) {
        build.onResolve({ filter: /^leaf:lit$/ }, () => ({
          path: "lit",
          namespace: "leaf-lit",
        }));
        build.onLoad({ filter: /.*/, namespace: "leaf-lit" }, () => ({
          contents,
          resolveDir: root,
        }));
      },
    },
    adapt([
      {
        file: /[/\\]lit-html[/\\]directives[/\\]ref\.js$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "e&&void 0!==this.G&&this.rt(void 0)",
              "e&&this.rt(void 0)",
              "Lit ref",
            ),
            "rt(t){if(this.isConnected",
            "rt(t){if(void 0===this.G)return;if(this.isConnected",
            "Lit ref",
          ),
      },
      {
        file: /[/\\]lit-html[/\\]lit-html\.js$/,
        edit: (source) =>
          move +
          seam(
            source,
            "this._$AA.parentNode.insertBefore(t,this._$AB)",
            "leafMove(this._$AA.parentNode,t,this._$AB)",
            "Lit move",
          ),
      },
      {
        file: /[/\\]lit-html[/\\]directive-helpers\.js$/,
        edit: (source) =>
          move + seam(source, "e.insertBefore(o,l)", "leafMove(e,o,l)", "Lit move"),
      },
    ]),
  ];
}

// Every schema a page's log at the current protocol relies on, and every record's,
// as it last stood (`protocol.mjs`). It is an output, so a build that passes moves it
// forward. A build refuses a change that breaks it.
const baselineName = "build/browser/protocol-baseline.json";

// JSON with a key per line to `depth` levels and each value below on one line, so the
// baseline's diff names the event kinds and records a change moved.
function layout(value, depth, indent = "") {
  if (!depth || value === null || typeof value !== "object" || Array.isArray(value))
    return JSON.stringify(value);
  const inner = `${indent}  `;
  const entries = Object.entries(value).map(
    ([key, item]) =>
      `${inner}${JSON.stringify(key)}: ${layout(item, depth - 1, inner)}`,
  );
  return `{\n${entries.join(",\n")}\n${indent}}`;
}

async function protocolOutputs() {
  const schemas = await protocolSchemas(new URL("../../", import.meta.url));
  const baseline = JSON.parse(await readFile(path.join(root, baselineName), "utf8"));
  const held = baselineSchemas(schemas);
  const refused = protocolBreaks(baseline, held);
  if (refused.length)
    throw new Error(
      `A page's log at protocol ${baseline.protocol}, or a Leaf sharing a record's format, breaks on:\n${refused.join("\n")}\nKeep what it took, or bump $events.protocol in browser/runtime/kernel-registry.json (for a record, set its since to the current protocol), then run pnpm run build:browser.`,
    );
  return {
    contract: await contractTypes(new URL("../../", import.meta.url), schemas),
    baseline: `${layout(held, 3)}\n`,
  };
}

// Two programs type-check the browser code, and each file has one checker.
// `tsconfig.json` holds the runtime modules that opt in with a leading `// @ts-check`
// to strict mode; it includes every runtime module so that each one opting in is
// checked there. Every framework module must opt in (`frameworkOptsIn`).
// `tsconfig.runtime.json` checks without it the rest of the runtime's modules,
// `leaf.js`, the kernel's and packages' widget modules, and the render checks pages
// import from `/checks/`. The `paths` both share
// resolve the rooted paths a page serves, a package's `vendor/` and `widgets/` among
// them, and map the framework's bundles, `/vendor/lit.js` and `/vendor/signals-core.js`,
// to declarations of the packages they bundle, so no declaration file ships in the
// layer. A relative path to one reaches the minified bundle, which carries no types.
// `runtime-globals.d.ts` declares what the classic scripts hang on `<html>` and
// `window`, the events the runtime dispatches with a detail, and the runtime's own
// elements by tag. tsc checks a JavaScript file wherever an import reaches it,
// with the options of the program it is in, and has no per-file opt-out, so the
// runtime program also reaches the strict program's files and the vendored
// third-party bundles. A diagnostic there is not the runtime program's to report, and
// the build drops it.
const strict = (file) =>
  readFileSync(path.join(root, file), "utf8").startsWith("// @ts-check");
const runtimeChecks = (file) =>
  file.endsWith(".js") &&
  !/^(?:browser|packages\/[^/]+)\/vendor\//.test(file) &&
  !strict(file);

/** Refuse a framework module that doesn't opt into the strict program, since the
 * framework's types are strict wherever it puts a module. */
async function frameworkOptsIn() {
  const modules = [
    `${assets}/runtime/framework.js`,
    ...(
      await readdir(path.join(root, assets, "runtime/framework"), { recursive: true })
    )
      .filter((name) => name.endsWith(".js"))
      .map((name) => `${assets}/runtime/framework/${name}`),
  ];
  const lax = modules.filter((file) => !strict(file));
  if (lax.length)
    throw new Error(
      `Start each framework module with \`// @ts-check\`, so the strict program checks it:\n${lax.join("\n")}`,
    );
}

function typecheck(config, reports = () => true) {
  const result = spawnSync(
    process.execPath,
    [
      path.join(root, "node_modules/typescript/bin/tsc"),
      "--project",
      `${typeRoot}/${config}`,
      "--pretty",
      "false",
    ],
    { cwd: root, encoding: "utf8" },
  );
  if (result.error) throw result.error;
  if (result.signal) throw new Error(`${config}: tsc ended on ${result.signal}`);
  if (result.status === 0) return;
  // Each diagnostic starts unindented, with its file where it has one; its
  // continuation lines indent.
  const diagnostics = (result.stdout + result.stderr)
    .split(/\n(?=\S)/)
    .filter((diagnostic) => {
      if (!diagnostic.trim()) return false;
      const file = /^(\S+)\(\d+,\d+\): /.exec(diagnostic)?.[1];
      return file === undefined || reports(file);
    });
  if (diagnostics.length) throw new Error(`${config}:\n${diagnostics.join("\n")}`);
}

export async function buildOutputs() {
  const paths = await compilerPaths();
  if (!(await readFile(path.join(root, compilerPathsFile))).equals(paths))
    throw new Error("Stale compiler paths; run pnpm run build:browser");
  const lit = await litTypes();
  if (!(await readFile(path.join(root, litTypesFile))).equals(lit))
    throw new Error("Stale Lit types; run pnpm run build:browser");
  const contractPath = path.join(root, typeRoot, "contract.d.ts");
  const protocol = await protocolOutputs();
  if ((await readFile(contractPath, "utf8")) !== protocol.contract)
    throw new Error("Stale protocol types; run pnpm run build:browser");
  await frameworkOptsIn();
  typecheck("tsconfig.json");
  typecheck("tsconfig.runtime.json", runtimeChecks);

  const outputs = new Map([
    [compilerPathsFile, paths],
    [litTypesFile, lit],
    [baselineName, Buffer.from(protocol.baseline)],
  ]);
  const result = await build({
    absWorkingDir: root,
    entryPoints: {
      [signalsPath.slice("vendor/".length, -".js".length)]: "leaf:signals",
    },
    outdir: `${assets}/vendor`,
    plugins: [
      {
        name: "shared-signals",
        setup(build) {
          build.onResolve({ filter: /^leaf:signals$/ }, () => ({
            path: "signals",
            namespace: "leaf-signals",
          }));
          build.onLoad({ filter: /.*/, namespace: "leaf-signals" }, () => ({
            // The package barrel also initializes its optional template directives,
            // pulling another Lit into this bundle. Build the published mixin alone.
            contents:
              'export * from "@preact/signals-core"; export { SignalWatcher } from ' +
              JSON.stringify(
                fileURLToPath(
                  new URL(
                    "./lib/signal-watcher.js",
                    import.meta.resolve("@lit-labs/preact-signals"),
                  ),
                ),
              ) +
              ";",
            resolveDir: root,
            loader: "js",
          }));
        },
      },
    ],
    platform: "browser",
    format: "esm",
    target: "es2022",
    bundle: true,
    minify: true,
    legalComments: "eof",
    metafile: true,
    write: false,
    logLevel: "silent",
  });
  for (const file of result.outputFiles) {
    const name = path.relative(root, file.path).split(path.sep).join("/");
    if (result.metafile.outputs[name].imports.length)
      throw new Error(`${name} imports another module`);
    checkModule(file.text, name);
    outputs.set(name, Buffer.from(file.contents));
  }
  const moduleLit = await build({
    absWorkingDir: root,
    stdin: {
      contents: `export * from "leaf:lit";`,
      resolveDir: root,
      sourcefile: "leaf-module-lit.js",
    },
    outfile: `${assets}/${litPath}`,
    plugins: await litModule(),
    platform: "browser",
    format: "esm",
    target: "es2022",
    bundle: true,
    minify: true,
    legalComments: "eof",
    metafile: true,
    write: false,
    logLevel: "silent",
  });
  const [moduleLitFile] = moduleLit.outputFiles;
  checkModule(moduleLitFile.text, litPath);
  outputs.set(`${assets}/${litPath}`, Buffer.from(moduleLitFile.contents));
  // Each served bundle's notices, named after it.
  for (const [name, metafile] of [
    ["signals-core", result.metafile],
    ["lit", moduleLit.metafile],
  ])
    outputs.set(
      `${assets}/vendor/${name}.LICENSES.txt`,
      Buffer.from(licenseNotices(name, bundledPackages(metafile, root))),
    );
  for (const producer of [styleOutputs, vendorOutputs])
    for (const [name, bytes] of await producer()) outputs.set(name, bytes);
  for (const [name, bytes] of await kernelOf(outputs))
    outputs.set(`${kernelDirectory}/${name}`, bytes);
  return outputs;
}

/**
 * The kernel (`runtime-bundle.mjs`, `kernelOutputs`) compiled from the layer this
 * build leaves: the tracked modules with every output above in place, and the
 * layer's `vendor/` as the build writes it, so one build both moves a module the
 * kernel reads and compiles the kernel from it.
 */
async function kernelOf(outputs) {
  const layer = await mkdtemp(path.join(tmpdir(), "leaf-kernel-layer-"));
  try {
    for (const name of ["leaf.js", "runtime", "widgets"])
      await cp(path.join(root, assets, name), path.join(layer, name), {
        recursive: true,
      });
    await mkdir(path.join(layer, "vendor"));
    for (const [name, bytes] of outputs) {
      if (!name.startsWith(`${assets}/`)) continue;
      const destination = path.join(layer, name.slice(assets.length + 1));
      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(destination, bytes);
    }
    return await kernelOutputs(layer);
  } finally {
    await rm(layer, { force: true, recursive: true });
  }
}

const missing = (error) => {
  if (error.code !== "ENOENT") throw error;
  return [];
};

/**
 * The directories this build owns whole: the kernel, the layer's `vendor/` and each
 * package's. Every file in them is an output, so one the build no longer writes is
 * stale.
 */
async function ownedDirectories(directory) {
  return [
    kernelDirectory,
    `${assets}/vendor`,
    ...(await packageDirectories(directory)).map((base) => `${base}/vendor`),
  ];
}

export async function checkOutputs(outputs, directory = root) {
  const stale = [];
  for (const owned of await ownedDirectories(directory))
    for (const file of await readdir(path.join(directory, owned), {
      recursive: true,
      withFileTypes: true,
    }).catch(missing))
      if (file.isFile()) {
        const name = path
          .relative(directory, path.join(file.parentPath, file.name))
          .split(path.sep)
          .join("/");
        if (!outputs.has(name)) stale.push(name);
      }
  for (const [name, expected] of outputs) {
    let actual;
    try {
      actual = await readFile(path.join(directory, name));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    if (!actual?.equals(expected)) stale.push(name);
  }
  // After a merge, a conflicted kernel file is one of these: the rebuild resolves it.
  if (stale.length)
    throw new Error(
      `Stale browser output; rebuild it with \`pnpm install --frozen-lockfile && pnpm run build:browser\`:\n${stale.join("\n")}`,
    );
}

async function main(args) {
  const usage = "Usage: node build/browser/build.mjs [--check]";
  if (args.length === 1 && args[0] === "--help") {
    console.log(
      `${usage}\n\nBuild committed browser ESM, or check it without writing. Run pnpm install --frozen-lockfile first.`,
    );
    return;
  }
  if (args.length > 1 || (args.length && args[0] !== "--check")) throw new Error(usage);
  if (args[0] !== "--check") {
    await writeFile(path.join(root, compilerPathsFile), await compilerPaths());
    await writeFile(path.join(root, litTypesFile), await litTypes());
    const { contract } = await protocolOutputs();
    await writeFile(path.join(root, typeRoot, "contract.d.ts"), contract);
  }
  const outputs = await buildOutputs();
  if (args[0] === "--check") await checkOutputs(outputs);
  else {
    for (const owned of await ownedDirectories(root))
      await rm(path.join(root, owned), { force: true, recursive: true });
    for (const [name, bytes] of outputs) {
      const destination = path.join(root, name);
      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(destination, bytes);
    }
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
