/** Bundle the published runtime and advertise its initial static import graph.
 *
 * HTML modulepreloads name the exact release-addressed modules the runtime will
 * import, including native vendor dependencies. Optional dynamic imports keep
 * their existing demand boundary. Import maps precede these links so preloading
 * cannot resolve a module against a different map than its ordinary execution.
 * The compiler supplies static edges; each document selects its widget entries.
 */

import { readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

import { bundleRuntime, runtimeEntries } from "../build/runtime-bundle.mjs";
import { widgetImports } from "../browser/runtime/widget-imports.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Published documents select a captured entry; never write through shared links. */
async function preloadDocuments(pageRoot, layers) {
  const documents = [];
  const directories = [pageRoot];
  for (const name of await readdir(pageRoot))
    if (name === "revisions" || name === "versions")
      directories.push(join(pageRoot, name));
  for (const directory of directories) {
    for (const file of await readdir(directory, { withFileTypes: true }))
      if (file.isFile() && file.name.endsWith(".html"))
        documents.push(join(directory, file.name));
  }
  for (const path of documents) {
    const source = await readFile(path, "utf8");
    const dom = new JSDOM(source, {
      includeNodeLocations: true,
      url: "https://leaf.invalid",
    });
    try {
      const markup = dom.window.document;
      const entry = markup
        .querySelector('script[type="module"][data-lf-runtime]')
        ?.getAttribute("src");
      const layer = layers.get(entry);
      if (!layer) throw new Error(`document has no bundled runtime entry: ${path}`);
      const { layerRoot, assetRoot, graph } = layer;
      const importMap = markup.querySelector(
        'script[type="importmap"][data-lf-runtime]',
      );
      if (!importMap) throw new Error(`document has no import map: ${path}`);
      const insertion = dom.nodeLocation(importMap).endOffset;
      const edits = [
        ...markup.querySelectorAll(
          'link[data-lf-runtime][rel="preload"], link[data-lf-runtime][rel="modulepreload"]',
        ),
      ].map((node) => ({ ...dom.nodeLocation(node), text: "" }));
      layer.registry ??= JSON.parse(
        await readFile(join(layerRoot, "registry.json"), "utf8"),
      );
      const required = widgetImports(markup.body, layer.registry);
      const pending = [
        "leaf.js",
        ...required.modules.map((tag) => `widgets/${tag}.js`),
      ].toReversed();
      const modules = new Set();
      while (pending.length) {
        const module = pending.pop();
        if (modules.has(module)) continue;
        const dependencies = graph.get(module);
        if (!dependencies)
          throw new Error(`initial runtime import has no captured module: ${module}`);
        modules.add(module);
        pending.push(...dependencies);
      }
      const probe = markup
        .querySelector("script[data-lf-runtime][data-lf-probe]")
        ?.getAttribute("data-lf-probe");
      if (!probe) throw new Error(`document has no registry address: ${path}`);
      const links = [
        `<link rel="preload" as="fetch" href="${probe.replaceAll("&", "&amp;")}" crossorigin data-lf-runtime>`,
        ...[...modules].map(
          (module) =>
            `<link rel="modulepreload" href="${`${assetRoot}/${module}`.replaceAll("&", "&amp;")}" data-lf-runtime>`,
        ),
      ].join("");
      // First-paint scripts write template openers at execution time. Edit only
      // the parser's actual hint/map locations, preserving every authored byte.
      edits.push({ startOffset: insertion, endOffset: insertion, text: links });
      edits.sort((a, b) => b.startOffset - a.startOffset || b.endOffset - a.endOffset);
      let document = source;
      for (const { startOffset, endOffset, text } of edits)
        document = document.slice(0, startOffset) + text + document.slice(endOffset);
      await rm(path);
      await writeFile(path, document);
    } finally {
      dom.window.close();
    }
  }
}

export async function bundleLayer(layerRoot, assetRoot, outputRoot = layerRoot) {
  const entries = [...runtimeEntries];
  for (const file of await readdir(join(layerRoot, "widgets"))) {
    if (file.endsWith(".js")) entries.push(`widgets/${file}`);
  }
  return bundleRuntime(layerRoot, entries, outputRoot, assetRoot);
}

export async function bundleSite(assets) {
  const manifest = JSON.parse(
    await readFile(join(assets, "_leaf", "site.json"), "utf8"),
  );
  for (const [route, page] of Object.entries(manifest.pages)) {
    const pageRoot = route === "/" ? assets : join(assets, route.slice(1));
    const revisions = join(pageRoot, "revisions");
    const layers = new Map();
    for (const revision of await readdir(revisions, { withFileTypes: true })) {
      if (!revision.isDirectory()) continue;
      const layerRoot = join(revisions, revision.name);
      const assetRoot = `${page.assets}/revisions/${revision.name}`;
      const graph = await bundleLayer(layerRoot, assetRoot);
      layers.set(`${assetRoot}/leaf.js`, { layerRoot, assetRoot, graph });
    }
    await preloadDocuments(pageRoot, layers);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await bundleSite(resolve(process.argv[2] ?? join(ROOT, ".tmp", "site-assets")));
}
