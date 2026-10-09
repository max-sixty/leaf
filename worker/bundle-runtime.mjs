/** Bundle the published runtime and advertise its initial static import graph.
 *
 * HTML modulepreloads name the exact release-addressed modules the runtime will
 * import, including native vendor dependencies. Optional dynamic imports keep
 * their existing demand boundary. Import maps precede these links so preloading
 * cannot resolve a module against a different map than its ordinary execution.
 */

import { readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { Window } from "happy-dom";

import { bundleRuntime, runtimeEntries } from "../build/runtime-bundle.mjs";
import { widgetImports } from "../skills/leaf/assets/runtime/widget-imports.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Read initial work through the document's generated rooted import map. */
export async function initialModules(layerRoot, assetRoot, imports, entries) {
  const origin = "https://leaf.invalid";
  const mappings = Object.entries(imports)
    .map(([name, target]) => [new URL(name, origin).href, new URL(target, origin).href])
    .sort(([left], [right]) => right.length - left.length);
  const resolveImport = (specifier, parent) => {
    const address = new URL(specifier, parent).href;
    for (const [name, target] of mappings) {
      if (address === name) return new URL(target);
      if (name.endsWith("/") && address.startsWith(name))
        return new URL(target + address.slice(name.length));
    }
    return new URL(address);
  };
  const pending = entries
    .toReversed()
    .map((entry) => resolveImport(entry, new URL(`${assetRoot}/`, origin)));
  const modules = new Set();
  while (pending.length) {
    const url = pending.pop();
    const address = url.pathname + url.search + url.hash;
    if (modules.has(address)) continue;
    if (url.origin !== origin || !url.pathname.startsWith(`${assetRoot}/`))
      throw new Error(`initial runtime import leaves its captured layer: ${url.href}`);
    modules.add(address);
    const source = await readFile(
      join(layerRoot, decodeURIComponent(url.pathname.slice(assetRoot.length + 1))),
      "utf8",
    );
    const module = parse(source, { ecmaVersion: "latest", sourceType: "module" });
    for (const node of module.body) {
      if (node.source) pending.push(resolveImport(node.source.value, url));
    }
  }
  return [...modules];
}

/** Published documents select a captured entry; never write through shared links. */
async function preloadDocuments(pageRoot, layers, parser) {
  const documents = [];
  const graphs = new Map();
  const registries = new Map();
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
    const source = (await readFile(path, "utf8")).replace(
      /<link rel="(?:modulepreload|preload)"[^>]* data-lf-runtime>/g,
      "",
    );
    const entry = source.match(
      /<script type="module" src="([^"]+)" data-lf-runtime>/,
    )?.[1];
    if (!entry) throw new Error(`document has no runtime entry: ${path}`);
    const layerRoot = layers.get(entry);
    if (!layerRoot) throw new Error(`document has no bundled runtime entry: ${path}`);
    const importMap = source.match(
      /<script type="importmap" data-lf-runtime>([\s\S]*?)<\/script>/,
    );
    if (!importMap) throw new Error(`document has no import map: ${path}`);
    if (!registries.has(layerRoot)) {
      registries.set(
        layerRoot,
        JSON.parse(await readFile(join(layerRoot, "registry.json"), "utf8")),
      );
    }
    const markup = parser.parseFromString(source, "text/html");
    const required = widgetImports(markup.body, registries.get(layerRoot));
    const entries = ["leaf.js", ...required.modules.map((tag) => `/widgets/${tag}.js`)];
    const graphKey = entry + importMap[1] + JSON.stringify(entries);
    if (!graphs.has(graphKey)) {
      graphs.set(
        graphKey,
        await initialModules(
          layerRoot,
          entry.slice(0, -"/leaf.js".length),
          JSON.parse(importMap[1]).imports,
          entries,
        ),
      );
    }
    const modules = graphs.get(graphKey);
    const probe = markup
      .querySelector("script[data-lf-runtime][data-lf-probe]")
      ?.getAttribute("data-lf-probe");
    if (!probe) throw new Error(`document has no registry address: ${path}`);
    const links = [
      `<link rel="preload" as="fetch" href="${probe.replaceAll("&", "&amp;")}" crossorigin data-lf-runtime>`,
      ...modules.map(
        (url) =>
          `<link rel="modulepreload" href="${url.replaceAll("&", "&amp;")}" data-lf-runtime>`,
      ),
    ].join("");
    const insertion = importMap.index + importMap[0].length;
    const document = source.slice(0, insertion) + links + source.slice(insertion);
    await rm(path);
    await writeFile(path, document);
  }
}

/** Advertise the emitted graph without rebuilding or changing any module byte. */
export async function preloadSite(assets) {
  const manifest = JSON.parse(
    await readFile(join(assets, "_leaf", "site.json"), "utf8"),
  );
  const window = new Window({
    settings: {
      enableJavaScriptEvaluation: false,
      disableJavaScriptFileLoading: true,
      disableCSSFileLoading: true,
      disableIframePageLoading: true,
      enableImageFileLoading: false,
    },
  });
  try {
    for (const [route, page] of Object.entries(manifest.pages)) {
      const pageRoot = route === "/" ? assets : join(assets, route.slice(1));
      const revisions = join(pageRoot, "revisions");
      const layers = new Map();
      for (const revision of await readdir(revisions, { withFileTypes: true })) {
        if (!revision.isDirectory()) continue;
        const assetRoot = `${page.assets}/revisions/${revision.name}`;
        layers.set(`${assetRoot}/leaf.js`, join(revisions, revision.name));
      }
      await preloadDocuments(pageRoot, layers, new window.DOMParser());
    }
  } finally {
    await window.happyDOM.close();
  }
}

export async function bundleLayer(layerRoot, assetRoot, outputRoot = layerRoot) {
  const entries = [...runtimeEntries];
  for (const file of await readdir(join(layerRoot, "widgets"))) {
    if (file.endsWith(".js")) entries.push(`widgets/${file}`);
  }
  await bundleRuntime(layerRoot, entries, outputRoot, assetRoot);
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
  await preloadSite(assets);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await bundleSite(resolve(process.argv[2] ?? join(ROOT, ".tmp", "site-assets")));
}
