/** Build the browser graph once, shared by website and prepared installations.
 *
 * Entry URLs are delivery boundaries; every other private module can move into
 * shared chunks. Both paths keep vendor modules native, at their public URL however
 * a runtime module names them, so a page loads one Lit, and each runtime module a
 * vendor module imports stays an entry at its own URL. Installations also retain
 * native package widgets, whose absolute URLs resolve through the revision's import
 * map, and the generation module, so page init can stamp it without rebuilding any
 * chunk. Preparation compiles the framework `build/browser/build.mjs` commits as
 * native modules into the kernel and drops its files, since only runtime modules
 * import it. The website captures layers a prepared installation vendored, which
 * already carry their generation, and compiles their kernel again with the widgets
 * while preserving authored module locations. Neither path runs on a user's machine.
 */

import { cp, mkdir, mkdtemp, readFile, readdir, realpath, rm } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { build } from "esbuild";
import { parse } from "acorn";

import { frameworkPaths, inFramework } from "./browser/build.mjs";

export const runtimeEntries = [
  "leaf.js",
  "runtime/interaction-gallery-frame.js",
  "runtime/layer-client.js",
  "runtime/media.js",
  "runtime/widget-api.js",
  "runtime/check-api.js",
];

const GENERATION = "runtime/layer-generation.js";

function browserPath(path) {
  return path.replaceAll("\\", "/");
}

function layerPath(path, assetRoot) {
  if (assetRoot && path.startsWith(`${assetRoot}/`))
    return path.slice(assetRoot.length + 1);
  return /^\/(?:runtime|vendor|widgets)\//.test(path) ? path.slice(1) : null;
}

/** Whether a layer module is served as committed rather than compiled into the kernel.
 *
 * Page modules and vendor modules always are; installations also keep package widgets
 * and the generation module native. The framework is not: the kernel absorbs it with
 * the runtime it imports.
 */
function native(local, assetRoot) {
  if (local.startsWith("page/")) return true;
  if (local.startsWith("vendor/")) return !inFramework(local);
  return !assetRoot && (local === GENERATION || local.startsWith("widgets/"));
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

/** Native modules' kernel imports are graph boundaries, not extra implementations. */
async function nativeRuntimeEntries(layerRoot, assetRoot) {
  const entries = new Set();
  for (const directory of ["vendor", "widgets"]) {
    const root = join(layerRoot, directory);
    for (const name of await readdir(root, { recursive: true })) {
      if (
        !name.endsWith(".js") ||
        !native(browserPath(join(directory, name)), assetRoot)
      )
        continue;
      const path = join(root, name);
      // Shipped vendor modules permit only static local imports (shipped.mjs).
      // Package modules' static declarations carry the same public API edge.
      const module = parse(await readFile(path, "utf8"), {
        ecmaVersion: "latest",
        sourceType: "module",
      });
      for (const node of module.body) {
        if (!node.source) continue;
        const specifier = node.source.value;
        const local = specifier.startsWith("/")
          ? layerPath(specifier, assetRoot)
          : specifier.startsWith(".")
            ? browserPath(relative(layerRoot, resolve(dirname(path), specifier)))
            : null;
        if (local?.startsWith("runtime/")) entries.add(local);
      }
    }
  }
  return [...entries].sort();
}

/** Compile one graph; an asset root names the website's fixed resource scope. */
export async function bundleRuntime(layerRoot, entries, outputRoot, assetRoot = null) {
  const inPlace = resolve(outputRoot) === resolve(layerRoot);
  layerRoot = await realpath(layerRoot);
  entries = [
    ...new Set([...entries, ...(await nativeRuntimeEntries(layerRoot, assetRoot))]),
  ];
  const entryPoints = Object.fromEntries(
    entries.map((path) => [path.slice(0, -3), join(layerRoot, path)]),
  );
  const modules = {
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

  const staging = await mkdtemp(join(tmpdir(), "leaf-runtime-bundle-"));
  try {
    await build({
      bundle: true,
      chunkNames: "runtime/bundle-[hash]",
      entryNames: "[dir]/[name]",
      entryPoints,
      format: "esm",
      legalComments: "none",
      minify: true,
      outdir: staging,
      platform: "browser",
      plugins: [modules],
      splitting: true,
    });
    if (inPlace) {
      const runtime = join(outputRoot, "runtime");
      await Promise.all(
        (await readdir(runtime, { recursive: true }))
          .filter((file) => file.endsWith(".js"))
          .map((file) => rm(join(runtime, file))),
      );
    }
    await cp(staging, outputRoot, { force: true, recursive: true });
    for (const path of frameworkPaths)
      await rm(join(outputRoot, path), { force: true, recursive: true });
  } finally {
    await rm(staging, { force: true, recursive: true });
  }
}

/** Prepared install output is relocatable; package modules need no build. */
export async function bundleDistribution(layerRoot, outputRoot) {
  layerRoot = await realpath(layerRoot);
  await bundleRuntime(
    layerRoot,
    [...runtimeEntries, "runtime/annotation-overlay/index.js"],
    outputRoot,
  );
  await mkdir(join(outputRoot, "runtime"), { recursive: true });
  for (const path of [
    GENERATION,
    "runtime/bootstrap.js",
    "runtime/prepaint.js",
    "runtime/offline-delivery.js",
    "runtime/image-difference.js",
  ])
    await cp(join(layerRoot, path), join(outputRoot, path));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 4)
    throw new Error("usage: node build/runtime-bundle.mjs INPUT OUTPUT");
  await bundleDistribution(resolve(process.argv[2]), resolve(process.argv[3]));
}
