import { link, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { expect, it } from "vitest";
import { Window } from "happy-dom";

import { preloadSite } from "../bundle-runtime.mjs";
import {
  registeredTags,
  widgetImports,
} from "../../skills/leaf/assets/runtime/widget-imports.js";

it("an arriving widget scope requires its own initializer and upgrade while template contents stay inert", async () => {
  const window = new Window();
  try {
    const scope = window.document.createElement("lf-arrival");
    scope.innerHTML =
      "<p>Prose</p><table></table><lf-unregistered></lf-unregistered><template><lf-unused></lf-unused></template>";
    const registry = {
      "lf-arrival": { "x-upgrade": true, "x-initial": "/widgets/initial.js" },
      "lf-unused": { "x-upgrade": true },
      table: { description: "A native table idiom.", "x-example": "<table></table>" },
      "lf-arrival.selected": {
        description: "A selected widget idiom.",
        "x-example": '<lf-arrival class="selected"></lf-arrival>',
      },
    };
    expect(registeredTags(scope, registry)).toEqual(["lf-arrival"]);
    expect(widgetImports(scope, registry)).toEqual({
      initializers: [{ tag: "lf-arrival", path: "/widgets/initial.js" }],
      modules: ["lf-arrival"],
    });
  } finally {
    await window.happyDOM.close();
  }
});

it("preloads each document's static graph without fetching optional modules or changing shared captures", async () => {
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
    const kernel = `${assetRoot}/revisions/r2-${"2".repeat(16)}`;
    const modules = new Map();
    for (const revision of [1, 2]) {
      const name = `r${revision}-${String(revision).repeat(16)}`;
      const layer = join(page, "revisions", name);
      const root = `${assetRoot}/revisions/${name}`;
      await mkdir(join(layer, "runtime"), { recursive: true });
      await mkdir(join(layer, "vendor"));
      await mkdir(join(layer, "widgets"));
      await writeFile(
        join(layer, "registry.json"),
        JSON.stringify({
          "lf-used": {
            "x-upgrade": revision === 1,
            ...(revision === 1 ? { "x-initial": "/vendor/initial.js" } : {}),
          },
          "lf-unused": { "x-upgrade": true },
        }),
      );
      const sources = {
        ...(revision === 2
          ? {
              "leaf.js": `import "./runtime/bundle-common.js"; export * from "${root}/vendor/framework.js"; export const optional = () => import("./runtime/optional.js");`,
              "runtime/bundle-common.js":
                'import "./bundle-cycle.js"; export const state = 1;',
              "runtime/bundle-cycle.js": 'export * from "./bundle-common.js";',
              "vendor/framework.js": 'export * from "/vendor/lit.js";',
              "vendor/lit.js": "export const html = 1;",
              "runtime/optional.js": "window.optionalLoaded = true;",
              "runtime/media.js": "export const media = 1;",
            }
          : {}),
        "widgets/lf-used.js": `import "/runtime/bundle-common.js"; import "${root}/vendor/widget.js"; export const optional = () => import("${kernel}/runtime/optional.js");`,
        "vendor/initial.js": `with ({ drawn: "initial-${revision}" }) { document.documentElement.dataset.drawn = drawn; }`,
        "vendor/widget.js": "export const widget = 1;",
      };
      for (const [name, source] of Object.entries(sources)) {
        const path = join(layer, name);
        await writeFile(path, source);
        modules.set(path, source);
      }
      const imports = {
        "/runtime/": `${kernel}/runtime/`,
        "/vendor/": `${kernel}/vendor/`,
      };
      const body = "<lf-used>Study</lf-used>";
      const initial =
        revision === 1
          ? `<script data-lf-runtime data-lf-initial>${sources["vendor/initial.js"]}</script>`
          : "";
      const source = `<html><head><script type="importmap" data-lf-runtime>${JSON.stringify({ imports })}</script><script data-lf-runtime data-lf-probe="${kernel}/registry.json" data-lf-vocabulary-root="${root}/registry.json">throw new Error("never execute authored scripts during the build");</script>${initial}<script type="module" src="${kernel}/leaf.js" data-lf-runtime></script></head><body>${body}<template><lf-unused></lf-unused></template></body></html>`;
      const shared = join(directory, `shared-${revision}.html`);
      await writeFile(shared, source);
      const paths = [
        join(page, "revisions", `${name}.html`),
        join(page, "versions", `v${revision}.html`),
        ...(revision === 2 ? [join(page, "index.html")] : []),
      ];
      for (const path of paths) await link(shared, path);
      documents.push({ source, shared, paths, root, revision });
    }

    // Running the stage again must retain one hint per module, even where the
    // publisher deduplicated the input HTML through shared hard links.
    await preloadSite(assets);
    await preloadSite(assets);

    for (const { source, shared, paths, root, revision } of documents) {
      expect(await readFile(shared, "utf8")).toBe(source);
      for (const path of paths) {
        const document = await readFile(path, "utf8");
        const preloads = [
          ...document.matchAll(/<link rel="modulepreload" href="([^"]+)"/g),
        ].map((match) => match[1]);
        expect(preloads.sort()).toEqual(
          [
            `${kernel}/leaf.js`,
            `${kernel}/runtime/bundle-common.js`,
            `${kernel}/runtime/bundle-cycle.js`,
            `${kernel}/vendor/framework.js`,
            `${kernel}/vendor/lit.js`,
            ...(revision === 1
              ? [`${root}/widgets/lf-used.js`, `${root}/vendor/widget.js`]
              : []),
          ].sort(),
        );
        expect(document.match(/<link rel="preload" as="fetch"[^>]+>/g)).toEqual([
          `<link rel="preload" as="fetch" href="${kernel}/registry.json" crossorigin data-lf-runtime>`,
          ...(revision === 1
            ? [
                `<link rel="preload" as="fetch" href="${root}/registry.json" crossorigin data-lf-runtime>`,
              ]
            : []),
        ]);
        expect(document.indexOf('rel="modulepreload"')).toBeGreaterThan(
          document.indexOf("</script>"),
        );
        expect(document.indexOf('rel="modulepreload"')).toBeLessThan(
          document.indexOf('type="module"'),
        );
        const window = new Window({ settings: { enableJavaScriptEvaluation: false } });
        try {
          const markup = window.document.createElement("template");
          markup.innerHTML = document;
          const initializer = markup.content.querySelector("script[data-lf-initial]");
          if (revision === 1) {
            expect(initializer?.textContent).toBe(
              modules.get(
                join(page, "revisions", `r1-${"1".repeat(16)}`, "vendor/initial.js"),
              ),
            );
            runInNewContext(initializer!.textContent, { document: window.document });
            expect(window.document.documentElement.dataset.drawn).toBe("initial-1");
          } else {
            expect(initializer).toBeNull();
          }
        } finally {
          await window.happyDOM.close();
        }
      }
    }
    for (const [path, source] of modules)
      expect(await readFile(path, "utf8")).toBe(source);
  } finally {
    await rm(directory, { recursive: true });
  }
});
