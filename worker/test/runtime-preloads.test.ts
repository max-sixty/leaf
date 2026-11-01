import { link, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, it } from "vitest";
import { Window } from "happy-dom";

import { bundleSite } from "../bundle-runtime.mjs";
import { registeredTags, widgetImports } from "../../browser/runtime/widget-imports.js";

it("an arriving widget scope requires its own upgrade while template contents stay inert", async () => {
  const window = new Window();
  try {
    const scope = window.document.createElement("lf-arrival");
    scope.innerHTML =
      "<p>Prose</p><table></table><lf-unregistered></lf-unregistered><template><lf-unused></lf-unused></template>";
    const registry: import("../../browser/runtime/widget-imports.js").Registry = {
      "lf-arrival": { "x-upgrade": true, "x-content": "empty" },
      "lf-unused": { "x-upgrade": true, "x-content": "empty" },
      table: {
        "x-upgrade": false,
        "x-content": "markup",
        "x-example": "<table></table>",
      },
      "lf-arrival.selected": {
        "x-upgrade": false,
        "x-content": "markup",
        "x-example": '<lf-arrival class="selected"></lf-arrival>',
      },
    };
    expect(registeredTags(scope, registry)).toEqual(["lf-arrival"]);
    expect(widgetImports(scope, registry)).toMatchObject({
      modules: ["lf-arrival"],
    });
  } finally {
    await window.happyDOM.close();
  }
});

it("bundles each document's static graph without fetching optional modules or changing shared captures", async () => {
  const directory = await mkdtemp(join(tmpdir(), "leaf-runtime-preloads-"));
  try {
    const assets = join(directory, "assets");
    const page = join(assets, "examples", "study");
    await mkdir(join(assets, "_leaf"), { recursive: true });
    await mkdir(join(page, "versions"), { recursive: true });
    const assetRoot = "/_leaf-release/release/study";
    await writeFile(
      join(assets, "_leaf", "site.json"),
      JSON.stringify({ pages: { "/examples/study": { assets: assetRoot } } }),
    );
    const documents = [];
    const modules = new Map();
    for (const revision of [1, 2]) {
      const name = `r${revision}-${String(revision).repeat(16)}`;
      const layer = join(page, "revisions", name);
      const root = `${assetRoot}/revisions/${name}`;
      await mkdir(join(layer, "runtime"), { recursive: true });
      await mkdir(join(layer, "vendor"));
      await mkdir(join(layer, "widgets"));
      await mkdir(join(layer, "page"));
      await writeFile(
        join(layer, "registry.json"),
        JSON.stringify({
          "lf-used": { "x-upgrade": true, "x-content": "empty" },
          "lf-unused": { "x-upgrade": true, "x-content": "empty" },
        }),
      );
      const sources = {
        "leaf.js": `import "./runtime/bundle-common.js"; export * from "${root}/vendor/framework.js"; export * from "${root}/page/app.mjs"; export const optional = () => import("./runtime/optional.js");`,
        "runtime/bundle-common.js":
          'import "./bundle-cycle.js"; export const state = 1;',
        "runtime/bundle-cycle.js": 'export * from "./bundle-common.js";',
        "vendor/framework.js":
          'export * from "/vendor/lit.js"; export * from "../runtime/media.js";',
        "vendor/lit.js": `import "./framework.js"; export * from "./revision-${revision}.js"; export const html = 1;`,
        [`vendor/revision-${revision}.js`]: `export const revision = ${revision};`,
        "runtime/optional.js": "window.optionalLoaded = true;",
        "runtime/media.js": "export const media = 1;",
        "runtime/layer-client.js": "export const client = 1;",
        "runtime/widget-api.js": "export const api = 1;",
        "runtime/portable-api.js": "export const portable = 1;",
        "runtime/check-api.js": "export const checks = 1;",
        "widgets/lf-used.js":
          'import "../runtime/bundle-common.js"; import "/vendor/widget.js"; export const optional = () => import("../runtime/optional.js");',
        "vendor/widget.js": "export const widget = 1;",
        "page/app.mjs": 'export * from "./state.js";',
        "page/state.js":
          'export * from "./values.mjs"; export const later = () => import("./optional.js");',
        "page/values.mjs": "export const value = 1;",
        "page/optional.js": "export const later = 1;",
        // Valid as a classic script, and deliberately absent from module roots.
        "page/classic.js": "var await = 1; window.classicLoaded = await;",
      };
      for (const [name, source] of Object.entries(sources)) {
        const path = join(layer, name);
        await writeFile(path, source);
        modules.set(path, source);
      }
      const imports = {
        "/vendor/": `${root}/vendor/`,
        "/widgets/": `${root}/widgets/`,
      };
      const body = revision === 2 ? "<lf-used>Study</lf-used>" : "Study";
      const authored = `<script>const mapMarker = '<script type="importmap" data-lf-runtime>'; const hintLiteral = '<link rel="modulepreload" href="${root}/leaf.js" data-lf-runtime>';</script>`;
      const importMap = `<script type="importmap" data-lf-runtime>${JSON.stringify({ imports })}</script>`;
      const prefix = `<!DOCTYPE html><html><!--${importMap}--><head>${authored}<link rel="stylesheet" href="${root}/leaf.css" data-lf-runtime>${importMap}`;
      const source = `${prefix}<script data-lf-runtime data-lf-probe="${root}/registry.json">throw new Error("never execute authored scripts during the build");</script><script type="module" src="${root}/leaf.js" data-lf-runtime></script></head><body>${body}<template><lf-unused></lf-unused></template></body></html>`;
      const insertion = prefix.length;
      const shared = join(directory, `shared-${revision}.html`);
      await writeFile(shared, source);
      const paths = [
        join(page, "revisions", `${name}.html`),
        join(page, "versions", `v${revision}.html`),
        ...(revision === 2 ? [join(page, "index.html")] : []),
      ];
      for (const path of paths) await link(shared, path);
      documents.push({ source, shared, paths, root, revision, insertion });
    }

    // Running the stage again must retain one hint per module, even where the
    // publisher deduplicated the input HTML through shared hard links.
    await bundleSite(assets);
    await bundleSite(assets);

    for (const { source, shared, paths, root, revision, insertion } of documents) {
      expect(await readFile(shared, "utf8")).toBe(source);
      for (const path of paths) {
        const document = await readFile(path, "utf8");
        const suffix = source.slice(insertion);
        expect(document.slice(0, insertion)).toBe(source.slice(0, insertion));
        expect(document.endsWith(suffix)).toBe(true);
        const hints = document.slice(insertion, document.length - suffix.length);
        const preloads = [
          ...hints.matchAll(/<link rel="modulepreload" href="([^"]+)"/g),
        ].map((match) => match[1]);
        expect(preloads.sort()).toEqual(
          [
            `${root}/leaf.js`,
            `${root}/runtime/media.js`,
            `${root}/vendor/framework.js`,
            `${root}/vendor/lit.js`,
            `${root}/vendor/revision-${revision}.js`,
            `${root}/page/app.mjs`,
            `${root}/page/state.js`,
            `${root}/page/values.mjs`,
            ...(revision === 2
              ? [`${root}/widgets/lf-used.js`, `${root}/vendor/widget.js`]
              : []),
          ].sort(),
        );
        expect(hints.match(/<link rel="preload" as="fetch"[^>]+>/g)).toEqual([
          `<link rel="preload" as="fetch" href="${root}/registry.json" crossorigin data-lf-runtime>`,
        ]);
        expect(document.replace(hints, "")).toBe(source);
      }
    }
    for (const [path, source] of modules) {
      if (!path.includes("/vendor/") && !path.includes("/page/")) continue;
      expect(await readFile(path, "utf8")).toBe(source);
    }
  } finally {
    await rm(directory, { recursive: true });
  }
}, 30_000);
