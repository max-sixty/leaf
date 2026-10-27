/** Compile the browser kernel: the readable build committed for installs, and the
 * website's minified rebundle of the layers pages vendor.
 *
 * Entry URLs are delivery boundaries; every other private module can move into
 * shared chunks. Both builds keep vendor modules native, at their public URL however
 * a runtime module names them, so a page loads one Lit, and each runtime module a
 * vendor module imports stays an entry at its own URL. The kernel also leaves native
 * package widgets, whose absolute URLs resolve through the revision's import map.
 * It compiles in the framework's signals (`vendor/signals-core.js`), which only the
 * runtime imports, with the framework. The website publishes each revision with the
 * runtime a prepared installation serves beside its captured layer, and compiles that
 * kernel again with the widgets while preserving authored module locations. Neither
 * build runs on a user's machine.
 *
 * `build/browser/build.mjs` commits the kernel to `dist/kernel/`
 * (`kernelOutputs`) and checks it against a rebuild with every other committed
 * bundle, and an install serves it only while it matches the tree's modules
 * (`leaf.runtime_selection.read_runtime`). Its form is what keeps it committable: it is
 * unminified, so a runtime change moves the lines that compile from it rather than
 * the whole chunk. Rolldown names shared chunks from their modules, without content
 * hashes, and writes their references itself. A conflict is resolved by merging
 * the source and rebuilding.
 *
 * Shared chunks preserve one module instance across entry points, including the
 * runtime's public API and native packages. Compiling each entry independently
 * would duplicate that state; eagerly combining all entries would lose lazy loading.
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
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "rolldown";
import { parse } from "acorn";

import { signalsPath } from "./browser/build.mjs";

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
 * Page modules and vendor modules always are, but for the framework's signals, which
 * the kernel absorbs with the framework; installations also keep package widgets
 * native.
 */
function native(local, assetRoot) {
  if (local.startsWith("page/")) return true;
  if (local.startsWith("vendor/")) return local !== signalsPath;
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

/** Where a module awaits outside every function, or null.
 *
 * One such await anywhere in a build turns off rolldown's chunk optimization
 * (`mergeCommonChunks`, `avoidRedundantChunkLoads`) for every module in it, since
 * that is how rolldown keeps a waiting module's execution order, and it says
 * nothing. When leaf.js awaited at its top level, every page loaded eleven more
 * kernel chunks before it presented.
 */
function topLevelAwait(program) {
  const visit = (node) => {
    if (/Function/.test(node.type)) return null;
    if (
      node.type === "AwaitExpression" ||
      (node.type === "ForOfStatement" && node.await) ||
      (node.type === "VariableDeclaration" && node.kind === "await using")
    )
      return node;
    for (const value of Object.values(node))
      for (const child of [value].flat())
        if (typeof child?.type === "string") {
          const found = visit(child);
          if (found) return found;
        }
    return null;
  };
  return visit(program);
}

/** Keep native modules at their public URLs and compiled modules in one graph, and,
 * where `refuseAwaits`, refuse a compiled module that awaits at its top level
 * (`topLevelAwait`). */
function moduleBoundaries(layerRoot, assetRoot, refuseAwaits) {
  return {
    name: "leaf-module-boundaries",
    transform(code, path) {
      if (!refuseAwaits || !code.includes("await")) return null;
      const found = topLevelAwait(this.parse(code, { sourceType: "module" }));
      if (found)
        this.error(
          `${browserPath(relative(layerRoot, path))} awaits at its top level, which turns off the bundler's chunk merging for the whole build: await inside a function the module calls`,
          found.start,
        );
      return null;
    },
    resolveId(path, importer) {
      if (!importer || !/^[./]/.test(path)) return null;
      const rooted = path.startsWith("/");
      const local = rooted
        ? layerPath(path, assetRoot)
        : browserPath(relative(layerRoot, resolve(dirname(importer), path)));
      if (local === null) return { external: true, id: path };
      if (local.startsWith("../")) return null;
      if (!native(local, assetRoot)) return { id: join(layerRoot, local) };
      return { external: true, id: rooted ? path : `${assetRoot ?? ""}/${local}` };
    },
    async load(path) {
      if (!assetRoot || !path.endsWith(".js")) return null;
      let contents = await readFile(path, "utf8");
      const publicPath = `${assetRoot}/${browserPath(relative(layerRoot, path))}`;
      const url = `new URL(${JSON.stringify(publicPath)}, location.origin).href`;
      for (const [start, end] of moduleUrlReads(contents).reverse())
        contents = contents.slice(0, start) + url + contents.slice(end);
      return contents;
    },
  };
}

/** A JavaScript literal of a value `runtime/kernel-facts.js` exports. A `__proto__`
 * key is computed, so it stays an own key rather than setting the prototype. */
function literal(value) {
  if (value instanceof RegExp) return String(value);
  if (value instanceof Set) return `new Set(${literal([...value])})`;
  if (Array.isArray(value)) return `[${value.map(literal).join(", ")}]`;
  if (Object.is(value, -0)) return "-0";
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    Number.isFinite(value)
  )
    return JSON.stringify(value);
  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype)
    return `{${Object.entries(value)
      .map(([key, item]) => {
        const name = JSON.stringify(key);
        return `${key === "__proto__" ? `[${name}]` : name}: ${literal(item)}`;
      })
      .join(", ")}}`;
  const kind = Object.prototype.toString.call(value).slice(8, -1);
  const shown =
    typeof value !== "object"
      ? `${kind} ${String(value)}`
      : Object.getPrototypeOf(value) === null
        ? "an object with no prototype"
        : kind;
  throw new Error(
    `runtime/kernel-facts.js exports ${shown}, which has no literal here`,
  );
}

/**
 * Compile `runtime/kernel-facts.js` to the values it exports, so the kernel carries
 * the few facts the browser reads rather than the whole kernel registry. The module is
 * evaluated from a `data:` URL with its JSON imports inlined, so the values come from
 * the bytes on disk now, never from a module Node cached earlier in a long build.
 * Each file it inlines joins `read`, which `kernelOutputs` records as compiled in and
 * with its hash, so an edit to the registry serves the source modules, which read it,
 * until the kernel is rebuilt.
 */
function kernelFacts(layerRoot, read) {
  const facts = join(layerRoot, "runtime/kernel-facts.js");
  const dataUrl = (type, text) =>
    `data:${type};base64,${Buffer.from(text).toString("base64")}`;
  return {
    name: "leaf-kernel-facts",
    async load(path) {
      if (path !== facts) return null;
      let source = await readFile(path, "utf8");
      const imports = parse(source, { ecmaVersion: "latest", sourceType: "module" })
        .body.filter((node) => node.source)
        .reverse();
      for (const { source: specifier } of imports) {
        if (!specifier.value.endsWith(".json"))
          throw new Error(`${path} may import only JSON, not ${specifier.value}`);
        const file = resolve(dirname(path), specifier.value);
        const json = await readFile(file, "utf8");
        read.add(browserPath(relative(layerRoot, file)));
        source =
          source.slice(0, specifier.start) +
          JSON.stringify(dataUrl("application/json", json)) +
          source.slice(specifier.end);
      }
      const values = await import(dataUrl("text/javascript", source));
      return Object.entries(values)
        .map(([name, value]) => `export const ${name} = ${literal(value)};\n`)
        .join("");
    },
  };
}

/** Compile one graph in memory; an asset root names the website's resource scope. */
async function compile(layerRoot, entries, assetRoot, minify, refuseAwaits = true) {
  const native = await nativeRuntimeEntries(layerRoot, assetRoot);
  entries = [...new Set([...entries, ...native.entries])];
  const inlined = new Set();
  const result = await build({
    cwd: layerRoot,
    input: Object.fromEntries(
      entries.map((path) => [path.slice(0, -3), join(layerRoot, path)]),
    ),
    platform: "browser",
    makeAbsoluteExternalsRelative: false,
    tsconfig: false,
    preserveEntrySignatures: "strict",
    plugins: [
      kernelFacts(layerRoot, inlined),
      moduleBoundaries(layerRoot, assetRoot, refuseAwaits),
    ],
    output: {
      format: "esm",
      entryFileNames: "[name].js",
      chunkFileNames: minify ? "runtime/bundle-[hash].js" : "runtime/bundle-[name].js",
      minify,
      minifyInternalExports: minify,
      comments: false,
    },
    write: false,
  });
  return { ...result, nativeImports: native.imports, inlined };
}

/** The website's minified rebundle and static dependency graph, by layer path.
 *
 * The compiler owns emitted edges; the captured layer's native declarations supply
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
  for (const file of result.output) {
    const destination = join(outputRoot, file.fileName);
    await mkdir(dirname(destination), { recursive: true });
    // Revisions share unchanged files as hard links; replace a file, never write
    // through it into another revision.
    await rm(destination, { force: true });
    await writeFile(destination, file.code);
  }
  await rm(join(outputRoot, signalsPath), { force: true });
  const graph = result.nativeImports;
  for (const output of result.output)
    graph.set(
      output.fileName,
      output.imports.map((path) => layerPath(path, assetRoot) ?? path),
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
 * The record's `inputs` map every file the build reads, `leaf.js`, each `.js` under
 * `runtime/`, `vendor/` and `widgets/`, and each other file it compiles in, such as
 * the kernel registry `kernelFacts` inlines as values, to the SHA-256 of its bytes,
 * one line each, so branches that change different modules change different lines.
 * The guard hashes each `.js` module and each other file the record names, so it
 * follows what this build read.
 * `replaces` lists the files compiled into the kernel, the kernel registry among them,
 * which a runtime serving it no longer carries. The modules it leaves native, such as the classic scripts
 * nothing imports, are served from source beside it.
 */
export async function kernelOutputs(layerRoot, { refuseAwaits = true } = {}) {
  layerRoot = await realpath(layerRoot);
  const entries = [...runtimeEntries];
  for (const entry of diagnosticEntries) {
    try {
      if ((await stat(join(layerRoot, entry))).isFile()) entries.push(entry);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  const result = await compile(layerRoot, entries, null, false, refuseAwaits);
  const files = new Map(
    result.output.map((file) => [file.fileName, Buffer.from(file.code)]),
  );
  const replaces = new Set([
    ...result.output
      .flatMap((file) => file.moduleIds)
      .filter((path) => path.startsWith(layerRoot + "/"))
      .map((path) => browserPath(relative(layerRoot, path))),
    ...result.inlined,
  ]);
  // Every file the compiler read, whatever its type, so an edit to any of them makes
  // the kernel stale.
  const modules = [
    ...new Set([...(await layerModules(layerRoot)), ...replaces]),
  ].sort();
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
  // A comparison arm's kernel (dev/leaf_dev/commands/distribution.py), which may be
  // an older tree's whose modules await at their top level: it still compiles, as
  // that tree's own build compiled it. This tree's build refuses one.
  const files = await kernelOutputs(resolve(process.argv[2]), { refuseAwaits: false });
  await rm(kernel, { force: true, recursive: true });
  for (const [name, bytes] of files) {
    await mkdir(dirname(join(kernel, name)), { recursive: true });
    await writeFile(join(kernel, name), bytes);
  }
}
