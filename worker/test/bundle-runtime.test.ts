import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import { bundleLayer, bundleSite } from "../bundle-runtime.mjs";

const temporary: string[] = [];

afterEach(async () => {
  await Promise.all(temporary.splice(0).map((path) => rm(path, { recursive: true })));
});

describe("published runtime bundle", () => {
  it("bundles every captured layer without absorbing shared page modules", async () => {
    const directory = await mkdtemp(join(tmpdir(), "leaf-revision-bundles-"));
    temporary.push(directory);
    const assetRoot = "/_leaf-release/release/study";
    await mkdir(join(directory, "_leaf"));
    await writeFile(
      join(directory, "_leaf", "site.json"),
      JSON.stringify({ pages: { "/examples/study": { assets: assetRoot } } }),
    );
    const revisions = ["r1-1111111111111111", "r2-2222222222222222"];
    for (const revision of revisions) {
      const layer = join(directory, "examples", "study", "revisions", revision);
      const root = `${assetRoot}/revisions/${revision}`;
      for (const sub of ["runtime", "widgets", "page"]) {
        await mkdir(join(layer, sub), { recursive: true });
      }
      await writeFile(
        join(layer, "leaf.js"),
        `import { state } from "${root}/page/state.js"; console.log(state);`,
      );
      for (const entry of [
        "interaction-gallery-frame",
        "layer-client",
        "media",
        "widget-api",
      ]) {
        await writeFile(
          join(layer, "runtime", `${entry}.js`),
          `export const revision = "${revision}";`,
        );
      }
      await writeFile(
        join(layer, "widgets", "lf-study.js"),
        `import { state } from "${root}/page/state.js"; console.log(state);`,
      );
      await writeFile(
        join(layer, "page", "state.js"),
        `export const state = { revision: "${revision}" };`,
      );
    }

    await bundleSite(directory);

    for (const revision of revisions) {
      const layer = join(directory, "examples", "study", "revisions", revision);
      const root = `${assetRoot}/revisions/${revision}`;
      for (const entry of ["leaf.js", "widgets/lf-study.js"]) {
        const bundled = await readFile(join(layer, entry), "utf8");
        expect(bundled).toContain(`from"${root}/page/state.js"`);
        expect(bundled).not.toContain("revision:");
      }
      expect(await readFile(join(layer, "page", "state.js"), "utf8")).toBe(
        `export const state = { revision: "${revision}" };`,
      );
      expect(
        await readFile(join(layer, "runtime", "layer-client.js"), "utf8"),
      ).toContain(revision);
    }
  });

  it("collapses static modules without changing their URL base", async () => {
    const directory = await mkdtemp(join(tmpdir(), "leaf-runtime-"));
    temporary.push(directory);
    const runtime = fileURLToPath(new URL("../../skills/leaf/assets", import.meta.url));

    await bundleLayer(runtime, "/published/layer", directory);
    const bundled = await readFile(join(directory, "leaf.js"), "utf8");
    const chunks = (
      await Promise.all(
        (await readdir(join(directory, "runtime")))
          .filter((file) => file.startsWith("bundle-"))
          .map((file) => readFile(join(directory, "runtime", file), "utf8")),
      )
    ).join("\n");

    expect(bundled).toContain(
      'from"/published/layer/runtime/chrome.css"with{type:"css"}',
    );
    expect(chunks).toContain(
      'from"/published/layer/runtime/marks.css"with{type:"css"}',
    );
    expect(chunks).toContain(
      'new URL("/published/layer/runtime/media.js",location.origin).href',
    );
    expect(await readFile(join(directory, "runtime", "media.js"), "utf8")).toBeTruthy();
    expect(
      await readFile(join(directory, "runtime", "layer-client.js"), "utf8"),
    ).toBeTruthy();
    expect(bundled).not.toMatch(/from"\.\/runtime\/(?!bundle-)/);
    expect(
      await readFile(join(directory, "widgets", "lf-suggestion.js"), "utf8"),
    ).not.toContain("/runtime/widget-api.js");
  });

  it("keeps root-absolute styles inside the published layer", async () => {
    const directory = await mkdtemp(join(tmpdir(), "leaf-runtime-absolute-css-"));
    temporary.push(directory);
    const runtime = fileURLToPath(new URL("../../skills/leaf/assets", import.meta.url));
    const source = join(directory, "source");
    const output = join(directory, "output");
    await cp(runtime, source, { recursive: true });
    const leaf = join(source, "leaf.js");
    await writeFile(
      leaf,
      (await readFile(leaf, "utf8")).replace(
        '"./runtime/chrome.css"',
        '"/runtime/chrome.css"',
      ),
    );

    await bundleLayer(source, "/published/layer", output);

    const bundled = await readFile(join(output, "leaf.js"), "utf8");
    expect(bundled).toContain(
      'from"/published/layer/runtime/chrome.css"with{type:"css"}',
    );
    expect(bundled).not.toContain("../runtime/chrome.css");
  });
});
