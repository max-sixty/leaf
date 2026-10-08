/** Build the browser graph once, shared by website and prepared installations.
 *
 * Entry URLs are delivery boundaries; every other private module can move into
 * shared chunks. Installations retain native package widgets and vendor modules,
 * whose absolute URLs resolve through the revision's import map. The generation
 * module stays native so page init can stamp it without rebuilding any chunk.
 * Website captures already carry their generation and preserve authored module
 * locations while bundling widgets. Both minify the framework modules
 * `build/browser/build.mjs` commits readable; the rest of the vendor directory ships
 * as upstream published it. Neither path runs on a user's machine.
 */

import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { build, transform } from "esbuild";
import { parse } from "acorn";

import { frameworkModules } from "./browser/build.mjs";

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

/** Native modules' kernel imports are graph boundaries, not extra implementations. */
async function nativeRuntimeEntries(layerRoot) {
  const entries = new Set();
  for (const directory of ["vendor", "widgets"]) {
    const root = join(layerRoot, directory);
    for (const name of await readdir(root, { recursive: true })) {
      if (!name.endsWith(".js")) continue;
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
          ? layerPath(specifier, null)
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
  const entryPoints = Object.fromEntries(
    entries.map((path) => [path.slice(0, -3), join(layerRoot, path)]),
  );
  const modules = {
    name: "leaf-module-boundaries",
    setup(builder) {
      builder.onResolve({ filter: /^\// }, ({ kind, path }) => {
        if (kind === "entry-point") return null;
        const local = layerPath(path, assetRoot);
        // Authored and package modules must share the runtime's existing instance.
        // Their page dependencies and vendor imports retain their public URL.
        return local &&
          !local.startsWith("vendor/") &&
          !local.startsWith("page/") &&
          (assetRoot || (local !== GENERATION && !local.startsWith("widgets/")))
          ? { path: join(layerRoot, local) }
          : { external: true, path };
      });
      if (assetRoot) {
        builder.onLoad({ filter: /\.js$/ }, async ({ path }) => {
          const source = await readFile(path, "utf8");
          const publicPath = `${assetRoot}/${browserPath(relative(layerRoot, path))}`;
          return {
            contents: source.replaceAll(
              "import.meta.url",
              `new URL(${JSON.stringify(publicPath)}, location.origin).href`,
            ),
            loader: "js",
          };
        });
      } else {
        builder.onResolve({ filter: /^\./ }, ({ importer, path }) => {
          const local = browserPath(
            relative(layerRoot, resolve(dirname(importer), path)),
          );
          if (
            local === GENERATION ||
            local.startsWith("vendor/") ||
            local.startsWith("widgets/")
          )
            return { external: true, path: `/${local}` };
          return null;
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
    for (const path of frameworkModules) {
      const { code } = await transform(await readFile(join(layerRoot, path), "utf8"), {
        format: "esm",
        legalComments: "eof",
        minify: true,
      });
      const target = join(outputRoot, path);
      // A captured file may be a hard link another revision shares.
      await rm(target, { force: true });
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, code);
    }
  } finally {
    await rm(staging, { force: true, recursive: true });
  }
}

/** Prepared install output is relocatable; package modules need no build. */
export async function bundleDistribution(layerRoot, outputRoot) {
  layerRoot = await realpath(layerRoot);
  await bundleRuntime(
    layerRoot,
    [
      ...new Set([
        ...runtimeEntries,
        "runtime/annotation-overlay/index.js",
        ...(await nativeRuntimeEntries(layerRoot)),
      ]),
    ],
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
