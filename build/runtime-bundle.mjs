/** Compile the browser kernel: the readable build committed for installs, and the
 * website's minified rebundle of the layers pages vendor.
 *
 * Entry URLs are delivery boundaries; every other private module can move into
 * shared chunks. Both builds keep vendor modules native, at their public URL however
 * a runtime module names them, so a page loads one Lit, and each runtime module a
 * vendor module imports stays an entry at its own URL. The kernel also leaves native
 * package widgets, whose absolute URLs resolve through the revision's import map.
 * It compiles in the framework `build/browser/build.mjs` commits as native modules,
 * since only runtime modules import it. The website publishes each revision with the
 * runtime a prepared installation serves beside its captured layer, and compiles that
 * kernel again with the widgets while preserving authored module locations. Neither
 * build runs on a user's machine.
 *
 * `build/browser/build.mjs` commits the kernel to `dist/kernel/`
 * (`kernelOutputs`) and checks it against a rebuild with every other committed
 * bundle, and an install serves it only while it matches the tree's modules
 * (`leaf.runtime_selection.read_runtime`). Its form is what keeps it committable: it is
 * unminified, so a runtime change moves the lines that compile from it rather than
 * the whole chunk, and its chunks keep their names across rebuilds (`kernelOutputs`).
 * Replaying the 52 runtime pull requests before 2026-10-14, each committing its own
 * kernel, 2 of them conflicted in this form, against 30 with minified chunks and 26
 * with unminified chunks named by hash, and none merged cleanly into bytes a rebuild
 * would not make. A conflict is resolved by merging `main` and rebuilding. One file per entry, without shared chunks, was rejected: it
 * duplicated 169 modules across entries, gave package widgets a second Lit, and
 * made `leaf.js` 1.9 MB. A kernel CI commits to `main` after each runtime merge was
 * rejected for the commit and push credential every merge would need.
 */

import { createHash } from "node:crypto";
import {
  mkdir,
  readFile,
  readdir,
  realpath,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "./esbuild.mjs";
import { parse } from "acorn";

import { frameworkPaths, inFramework } from "./browser/build.mjs";

export const runtimeEntries = [
  "leaf.js",
  "runtime/layer-client.js",
  "runtime/media.js",
  "runtime/widget-api.js",
  "runtime/check-api.js",
];

// Historical comparison arms predate optional diagnostic capabilities. Compile
// the entries a layer supplies; the required delivery boundaries above stay strict.
const diagnosticEntries = ["runtime/annotation-overlay/check-api.js"];

function browserPath(path) {
  return path.replaceAll("\\", "/");
}

function layerPath(path, assetRoot) {
  if (assetRoot && path.startsWith(`${assetRoot}/`))
    return path.slice(assetRoot.length + 1);
  return /^\/(?:runtime|vendor|widgets|page)\//.test(path) ? path.slice(1) : null;
}

/** Whether a layer module is served as committed rather than compiled into the kernel.
 *
 * Page modules and vendor modules always are; installations also keep package widgets
 * native. The framework is not: the kernel absorbs it with the runtime it imports.
 */
function native(local, assetRoot) {
  if (local.startsWith("page/")) return true;
  if (local.startsWith("vendor/")) return !inFramework(local);
  return !assetRoot && local.startsWith("widgets/");
}

/** Where a module reads its own URL, as source ranges in order. */
function moduleUrlReads(source) {
  const ranges = [];
  const visit = (node) => {
    if (
      node.type === "MemberExpression" &&
      node.object.type === "MetaProperty" &&
      !node.computed &&
      node.property.name === "url"
    ) {
      ranges.push([node.start, node.end]);
      return;
    }
    for (const value of Object.values(node))
      for (const child of [value].flat())
        if (typeof child?.type === "string") visit(child);
  };
  visit(parse(source, { ecmaVersion: "latest", sourceType: "module" }));
  return ranges.sort(([a], [b]) => a - b);
}

/** Static declarations of one captured native module, resolved by layer path. */
async function nativeImports(layerRoot, local, assetRoot) {
  const path = join(layerRoot, local);
  const module = parse(await readFile(path, "utf8"), {
    ecmaVersion: "latest",
    sourceType: "module",
  });
  return module.body
    .filter((node) => node.source)
    .map((node) => {
      const specifier = node.source.value;
      return specifier.startsWith("/")
        ? (layerPath(specifier, assetRoot) ?? specifier)
        : specifier.startsWith(".")
          ? browserPath(relative(layerRoot, resolve(dirname(path), specifier)))
          : specifier;
    });
}

/** Retain native static edges and keep their runtime imports as kernel entries. */
async function nativeRuntimeEntries(layerRoot, assetRoot) {
  const entries = new Set();
  const imports = new Map();
  for (const directory of ["vendor", "widgets"]) {
    const root = join(layerRoot, directory);
    for (const name of await readdir(root, { recursive: true })) {
      const local = browserPath(join(directory, name));
      if (!/\.m?js$/.test(name) || !native(local, assetRoot)) continue;
      // Shipped vendor modules permit only static local imports (shipped.mjs).
      // Package declarations carry the same public API edge.
      const dependencies = await nativeImports(layerRoot, local, assetRoot);
      for (const dependency of dependencies)
        if (dependency.startsWith("runtime/")) entries.add(dependency);
      imports.set(local, dependencies);
    }
  }
  return { entries: [...entries].sort(), imports };
}

/** The esbuild plugin that keeps native modules outside the graph. */
function moduleBoundaries(layerRoot, assetRoot) {
  return {
    name: "leaf-module-boundaries",
    setup(builder) {
      // Authored and package modules must share the runtime's existing instance.
      // Native modules, which every page loads at their public URL, stay outside the
      // graph whether an import names them rooted or relative.
      builder.onResolve({ filter: /^[./]/ }, ({ kind, importer, path }) => {
        if (kind === "entry-point") return null;
        const rooted = path.startsWith("/");
        const local = rooted
          ? layerPath(path, assetRoot)
          : browserPath(relative(layerRoot, resolve(dirname(importer), path)));
        if (local === null) return { external: true, path };
        if (local.startsWith("../")) return null;
        if (!native(local, assetRoot)) return { path: join(layerRoot, local) };
        return { external: true, path: rooted ? path : `${assetRoot ?? ""}/${local}` };
      });
      if (assetRoot) {
        builder.onLoad({ filter: /\.js$/ }, async ({ path }) => {
          let contents = await readFile(path, "utf8");
          const publicPath = `${assetRoot}/${browserPath(relative(layerRoot, path))}`;
          const url = `new URL(${JSON.stringify(publicPath)}, location.origin).href`;
          for (const [start, end] of moduleUrlReads(contents).reverse())
            contents = contents.slice(0, start) + url + contents.slice(end);
          return { contents, loader: "js" };
        });
      }
    },
  };
}

// The directory, inside the layer, that output paths are relative to. Nothing is
// written there: each caller takes the outputs in memory.
const OUT = ".kernel";

/** Compile one graph in memory; an asset root names the website's resource scope. */
async function compile(layerRoot, entries, assetRoot, minify) {
  const native = await nativeRuntimeEntries(layerRoot, assetRoot);
  entries = [...new Set([...entries, ...native.entries])];
  const result = await build({
    // Metafile paths and unminified module comments name layer paths, not this host's.
    absWorkingDir: layerRoot,
    bundle: true,
    chunkNames: "runtime/bundle-[hash]",
    entryNames: "[dir]/[name]",
    entryPoints: Object.fromEntries(
      entries.map((path) => [path.slice(0, -3), join(layerRoot, path)]),
    ),
    format: "esm",
    legalComments: "none",
    logLevel: "silent",
    metafile: true,
    minify,
    outdir: join(layerRoot, OUT),
    platform: "browser",
    plugins: [moduleBoundaries(layerRoot, assetRoot)],
    splitting: true,
    write: false,
  });
  return { ...result, nativeImports: native.imports };
}

/** The website's minified rebundle and static dependency graph, by layer path.
 *
 * esbuild owns emitted edges; the captured layer's native declarations supply
 * external edges. Dynamic imports stay outside this initial-load graph.
 */
export async function bundleRuntime(layerRoot, entries, outputRoot, assetRoot) {
  const inPlace = resolve(outputRoot) === resolve(layerRoot);
  layerRoot = await realpath(layerRoot);
  const result = await compile(layerRoot, entries, assetRoot, true);
  if (inPlace) {
    const runtime = join(outputRoot, "runtime");
    await Promise.all(
      (await readdir(runtime, { recursive: true }))
        .filter((file) => file.endsWith(".js"))
        .map((file) => rm(join(runtime, file))),
    );
  }
  for (const file of result.outputFiles) {
    const destination = join(outputRoot, relative(join(layerRoot, OUT), file.path));
    await mkdir(dirname(destination), { recursive: true });
    // Revisions share unchanged files as hard links; replace a file, never write
    // through it into another revision.
    await rm(destination, { force: true });
    await writeFile(destination, file.contents);
  }
  for (const path of frameworkPaths)
    await rm(join(outputRoot, path), { force: true, recursive: true });
  const graph = result.nativeImports;
  for (const [path, output] of Object.entries(result.metafile.outputs))
    graph.set(
      browserPath(relative(OUT, path)),
      output.imports
        .filter(({ kind }) => kind === "import-statement")
        .map(({ path, external }) =>
          external
            ? (layerPath(path, assetRoot) ?? path)
            : browserPath(relative(OUT, path)),
        ),
    );
  // Authored page files also include classic scripts. Read only modules reached
  // by static declarations, including .mjs, rather than parsing that directory.
  const pending = [...graph.values()].flat();
  while (pending.length) {
    const local = pending.pop();
    if (graph.has(local)) continue;
    const dependencies = await nativeImports(layerRoot, local, assetRoot);
    graph.set(local, dependencies);
    pending.push(...dependencies);
  }
  return graph;
}

/** Every module a kernel build reads, by layer path, sorted. */
async function layerModules(layerRoot) {
  const modules = ["leaf.js"];
  for (const directory of ["runtime", "vendor", "widgets"])
    for (const name of await readdir(join(layerRoot, directory), { recursive: true }))
      if (name.endsWith(".js")) modules.push(browserPath(join(directory, name)));
  return modules.sort();
}

/**
 * The kernel built from one layer: each file by its layer path, and `kernel.json`,
 * the record an install's guard reads (`leaf.runtime_selection.read_runtime`).
 *
 * The record's `inputs` map every module the build reads, `leaf.js` and each `.js`
 * under `runtime/`, `vendor/` and `widgets/`, to the SHA-256 of its bytes, one line
 * each, so branches that change different modules change different lines.
 * `replaces` lists the modules compiled into the kernel, which a runtime serving it
 * no longer carries. The modules it leaves native, such as the classic scripts
 * nothing imports, are served from source beside it.
 *
 * esbuild names a split chunk only by its hash (`[name]` is `chunk` for every
 * chunk), and the hash moves whenever anything inside the chunk does, so every
 * runtime change would rename chunks and conflict with every other. Each chunk is
 * renamed after the first module in it, `bundle-<its path, / as ~>.js`, numbered
 * `-2`, `-3` in the order of their module lists where that name is already an
 * entry's, a layer module's or another chunk's, and every reference to it is
 * rewritten.
 */
export async function kernelOutputs(layerRoot) {
  layerRoot = await realpath(layerRoot);
  const entries = [...runtimeEntries];
  for (const entry of diagnosticEntries) {
    try {
      if ((await stat(join(layerRoot, entry))).isFile()) entries.push(entry);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  const result = await compile(layerRoot, entries, null, false);
  const outputs = Object.entries(result.metafile.outputs).map(([path, output]) => ({
    name: browserPath(relative(OUT, path)),
    output,
  }));
  // An entry keeps its own path. Every other output is a chunk named by hash: one a
  // dynamic import starts takes the name of the module it starts, and a chunk of
  // esbuild's own helpers, which holds no module, the name of its first export.
  const chunks = outputs
    .filter(({ name, output }) => name !== output.entryPoint)
    .map(({ name, output }) => ({
      name,
      modules: Object.keys(output.inputs),
      first: output.entryPoint ?? Object.keys(output.inputs)[0] ?? output.exports[0],
    }))
    .map((chunk) => ({ ...chunk, order: [...chunk.modules, chunk.first].join("\n") }))
    .sort((a, b) => (a.order < b.order ? -1 : a.order > b.order ? 1 : 0));
  // A chunk never takes the path of an entry or of any module in the layer.
  const modules = await layerModules(layerRoot);
  const taken = new Set([
    ...modules,
    ...outputs
      .filter(({ name, output }) => name === output.entryPoint)
      .map(({ name }) => name),
  ]);
  const renames = new Map();
  for (const { name, first } of chunks) {
    const stem = `runtime/bundle-${first
      .replace(/^runtime\//, "")
      .replace(/\.js$/, "")
      .replaceAll("/", "~")}`;
    let stable = `${stem}.js`;
    for (let n = 2; taken.has(stable); n++) stable = `${stem}-${n}.js`;
    taken.add(stable);
    renames.set(name, stable);
  }
  const files = new Map();
  for (const file of result.outputFiles) {
    const name = browserPath(relative(join(layerRoot, OUT), file.path));
    let text = file.text;
    for (const [hashed, stable] of renames)
      text = text.replaceAll(basename(hashed), basename(stable));
    files.set(renames.get(name) ?? name, Buffer.from(text));
  }
  const replaces = new Set(outputs.flatMap(({ output }) => Object.keys(output.inputs)));
  const inputs = {};
  for (const module of modules)
    inputs[module] = createHash("sha256")
      .update(await readFile(join(layerRoot, module)))
      .digest("hex");
  const record = { inputs, replaces: [...replaces].sort() };
  files.set("kernel.json", Buffer.from(`${JSON.stringify(record, null, 2)}\n`));
  return files;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 4)
    throw new Error("usage: node build/runtime-bundle.mjs LAYER KERNEL");
  const kernel = resolve(process.argv[3]);
  const files = await kernelOutputs(resolve(process.argv[2]));
  await rm(kernel, { force: true, recursive: true });
  for (const [name, bytes] of files) {
    await mkdir(dirname(join(kernel, name)), { recursive: true });
    await writeFile(join(kernel, name), bytes);
  }
}
