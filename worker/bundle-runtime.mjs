/** Bundle the published browser runtime while preserving its public module URLs. */

import { cp, mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { basename, dirname, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { build } from "esbuild";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function browserPath(path) {
  return path.replaceAll("\\", "/");
}

function layerPath(path, assetRoot) {
  const scopedPrefix = `${assetRoot}/`;
  if (path.startsWith(scopedPrefix)) return path.slice(scopedPrefix.length);
  return /^\/(?:runtime|vendor|widgets)\/(.+)$/.exec(path)?.[0].slice(1);
}

export async function bundleLayer(layerRoot, assetRoot, outputRoot = layerRoot) {
  const entries = {
    leaf: join(layerRoot, "leaf.js"),
    "runtime/interaction-gallery-frame": join(
      layerRoot,
      "runtime",
      "interaction-gallery-frame.js",
    ),
    "runtime/layer-client": join(layerRoot, "runtime", "layer-client.js"),
    "runtime/media": join(layerRoot, "runtime", "media.js"),
    "runtime/widget-api": join(layerRoot, "runtime", "widget-api.js"),
  };
  for (const file of await readdir(join(layerRoot, "widgets"))) {
    if (file.endsWith(".js")) {
      entries[`widgets/${basename(file, ".js")}`] = join(layerRoot, "widgets", file);
    }
  }

  const preserveUrls = {
    name: "preserve-module-urls",
    setup(builder) {
      builder.onResolve({ filter: /\.css$/ }, ({ importer, path }) => {
        if (path.startsWith("/")) {
          const local = layerPath(path, assetRoot);
          return {
            external: true,
            path: local ? `${assetRoot}/${local}` : path,
          };
        }
        const resolved = resolve(dirname(importer), path);
        const publicPath = `${assetRoot}/${browserPath(relative(layerRoot, resolved))}`;
        return { external: true, path: publicPath };
      });
      builder.onResolve({ filter: /^\// }, ({ kind, path }) => {
        if (kind === "entry-point") return null;
        const local = layerPath(path, assetRoot);
        // Authored modules also import these URLs directly. Bundling a page
        // dependency into a widget would create a second instance of its state.
        return local && !local.startsWith("vendor/") && !local.startsWith("page/")
          ? { path: join(layerRoot, local) }
          : { external: true, path };
      });
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
    },
  };

  const staging = await mkdtemp(join(tmpdir(), "leaf-runtime-bundle-"));
  try {
    await build({
      bundle: true,
      chunkNames: "runtime/bundle-[hash]",
      entryNames: "[dir]/[name]",
      entryPoints: entries,
      format: "esm",
      legalComments: "none",
      minify: true,
      outdir: staging,
      platform: "browser",
      plugins: [preserveUrls],
      splitting: true,
    });
    if (resolve(outputRoot) === resolve(layerRoot)) {
      const runtime = join(outputRoot, "runtime");
      await Promise.all(
        (await readdir(runtime, { recursive: true }))
          .filter((file) => file.endsWith(".js"))
          .map((file) => rm(join(runtime, file))),
      );
    }
    await cp(staging, outputRoot, { force: true, recursive: true });
  } finally {
    await rm(staging, { force: true, recursive: true });
  }
}

export async function bundleSite(assets) {
  const manifest = JSON.parse(
    await readFile(join(assets, "_leaf", "site.json"), "utf8"),
  );
  for (const [route, page] of Object.entries(manifest.pages)) {
    const pageRoot = route === "/" ? assets : join(assets, route.slice(1));
    const revisions = join(pageRoot, "revisions");
    for (const revision of await readdir(revisions, { withFileTypes: true })) {
      if (!revision.isDirectory()) continue;
      await bundleLayer(
        join(revisions, revision.name),
        `${page.assets}/revisions/${revision.name}`,
      );
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await bundleSite(resolve(process.argv[2] ?? join(ROOT, ".tmp", "site-assets")));
}
