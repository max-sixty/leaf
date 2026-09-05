// Experimental fixed-page bundle. No source runtime or widget is copied by hand.
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const [page, modules, output] = process.argv.slice(2);
const require = createRequire(path.join(modules, "../package.json"));
// Use the in-process browser/WASM API: this avoids a native service subprocess.
globalThis.self = globalThis;
const { build, initialize, stop } = require("esbuild-wasm/lib/browser.js");
await initialize({
  wasmModule: await WebAssembly.compile(
    await fs.readFile(require.resolve("esbuild-wasm/esbuild.wasm")),
  ),
  worker: false,
});
const registry = JSON.parse(
  await fs.readFile(path.join(page, "registry.json"), "utf8"),
);
const widgets = Object.entries(registry)
  .filter(([tag, entry]) => !tag.startsWith("$") && entry["x-upgrade"])
  .map(([tag]) => `/widgets/${tag}.js`);
const loaders = widgets
  .map((url) => `${JSON.stringify(url)}: () => import(${JSON.stringify(url)})`)
  .join(",\n");
const assets = {};
for (const [url, type] of [
  ["/registry.json", "application/json"],
  ["/theme.css", "text/css"],
  ["/icon.svg", "image/svg+xml"],
]) {
  assets[url] = { body: await fs.readFile(path.join(page, url), "utf8"), type };
}
const bootstrap = await fs.readFile(
  new URL("./direct-entry.js", import.meta.url),
  "utf8",
);
const iconUrl = `data:image/svg+xml;base64,${Buffer.from(assets["/icon.svg"].body).toString("base64")}`;
const result = await build({
  stdin: {
    contents: `const assetFiles = ${JSON.stringify(assets)};\nconst widgetModules = {${loaders}};\n${bootstrap}`,
    resolveDir: path.dirname(new URL(import.meta.url).pathname),
    sourcefile: "leaf-direct-entry.js",
  },
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "chrome120",
  minify: true,
  write: false,
  plugins: [
    {
      name: "vendored-leaf",
      setup(builder) {
        builder.onResolve({ filter: /.*/ }, ({ path: url, importer }) => {
          const filename = url.startsWith("/")
            ? path.join(page, url)
            : url.startsWith(".")
              ? path.resolve(path.dirname(importer), url)
              : require.resolve(url, { paths: [modules, path.dirname(importer)] });
          return { path: filename, namespace: "leaf-file" };
        });
        builder.onLoad(
          { filter: /.*/, namespace: "leaf-file" },
          async ({ path: filename }) => {
            let source = await fs.readFile(filename, "utf8");
            if (filename.endsWith("/runtime/widget-loader.js")) {
              const original = "import(`/widgets/${tag}.js`)";
              if (source.split(original).length !== 2)
                throw new Error("Widget import boundary changed");
              source = source.replace(
                original,
                "globalThis.leafProbeImport(`/widgets/${tag}.js`)",
              );
            }
            // These browser-managed loads do not pass through the fetch adapter.
            if (filename.endsWith("/runtime/banner.js")) {
              const original = 'href: "/icon.svg"';
              if (!source.includes(original))
                throw new Error("Favicon boundary changed");
              source = source.replace(original, `href: ${JSON.stringify(iconUrl)}`);
            }
            // A CSS module import (`with { type: "css" }`) hands the runtime a
            // constructed sheet. The bundle has no loader for one, so the file becomes
            // the module that constructs it, with the icon mask's URL inlined first.
            if (filename.endsWith(".css")) {
              const original = 'url("/icon.svg")';
              if (
                filename.endsWith("/runtime/chrome.css") &&
                !source.includes(original)
              )
                throw new Error("Icon mask boundary changed");
              source = source.replaceAll(original, `url("${iconUrl}")`);
              return {
                contents:
                  "const sheet = new CSSStyleSheet();\n" +
                  `sheet.replaceSync(${JSON.stringify(source)});\n` +
                  "export default sheet;\n",
                loader: "js",
              };
            }
            return {
              contents: source,
              loader: filename.endsWith(".json") ? "json" : "js",
            };
          },
        );
      },
    },
  ],
});
await fs.writeFile(output, result.outputFiles[0].text);
console.log(
  JSON.stringify({
    bundleBytes: result.outputFiles[0].contents.length,
    widgets: widgets.length,
  }),
);
await stop();
