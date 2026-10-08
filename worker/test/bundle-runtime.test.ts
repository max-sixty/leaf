import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

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
      for (const sub of ["runtime", "widgets", "page", "vendor/browser-runtime"]) {
        await mkdir(join(layer, sub), { recursive: true });
      }
      await writeFile(
        join(layer, "leaf.js"),
        `import { state } from "${root}/page/state.js"; import { moduleUrl } from "${root}/runtime/url.js"; import { framework } from "${root}/vendor/browser-runtime.js"; console.log(state, moduleUrl, framework, import.meta.url);`,
      );
      await writeFile(
        join(layer, "runtime", "url.js"),
        "export const moduleUrl = import.meta.url;",
      );
      for (const entry of [
        "interaction-gallery-frame",
        "layer-client",
        "media",
        "widget-api",
        "check-api",
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
      await writeFile(join(layer, "vendor", "lit.js"), "export const html = 1;\n");
      await writeFile(
        join(layer, "vendor", "browser-runtime.js"),
        `export { framework } from "${root}/vendor/browser-runtime/model.js";\n`,
      );
      await writeFile(
        join(layer, "vendor", "browser-runtime", "model.js"),
        `import { html } from "${root}/vendor/lit.js";\nexport const framework = html;\n`,
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
      expect(await readFile(join(layer, "leaf.js"), "utf8")).toContain(
        `new URL("${root}/leaf.js",location.origin).href`,
      );
      // The kernel absorbs the framework and keeps the page's one Lit.
      expect(await readFile(join(layer, "leaf.js"), "utf8")).toContain(
        `from"${root}/vendor/lit.js"`,
      );
      expect(await readdir(join(layer, "vendor"))).toEqual(["lit.js"]);
      expect(await readFile(join(layer, "leaf.js"), "utf8")).toContain(
        `new URL("${root}/runtime/url.js",location.origin).href`,
      );
      expect(await readFile(join(layer, "page", "state.js"), "utf8")).toBe(
        `export const state = { revision: "${revision}" };`,
      );
      expect(
        await readFile(join(layer, "runtime", "layer-client.js"), "utf8"),
      ).toContain(revision);
    }
  });

  it("collapses the production runtime's static modules", async () => {
    const directory = await mkdtemp(join(tmpdir(), "leaf-runtime-"));
    try {
      // The production layer is the kernel composed with its bundled packages.
      const runtime = join(directory, "layer");
      execFileSync(
        fileURLToPath(new URL("../../bin/leaf", import.meta.url)),
        ["page", "init", runtime],
        { env: { ...process.env, XDG_STATE_HOME: join(directory, "state") } },
      );

      const output = join(directory, "bundled");
      await bundleLayer(runtime, "/published/layer", output);
      const bundled = await readFile(join(output, "leaf.js"), "utf8");
      expect(await readFile(join(output, "runtime", "media.js"), "utf8")).toBeTruthy();
      expect(
        await readFile(join(output, "runtime", "layer-client.js"), "utf8"),
      ).toBeTruthy();
      expect(bundled).not.toMatch(/from"\.\/runtime\/(?!bundle-)/);
      // The kernel absorbs the framework; the page still shares one Lit.
      const kernel = (
        await Promise.all(
          (await readdir(join(output, "runtime")))
            .filter((file) => file.endsWith(".js"))
            .map((file) => readFile(join(output, "runtime", file), "utf8")),
        )
      ).join("\n");
      expect(kernel).toContain('"accepted:presented"');
      expect(kernel).toContain('from"/published/layer/vendor/lit.js"');
      expect(kernel).not.toContain("litHtmlVersions");
      expect(kernel).not.toContain("browser-runtime");
      // A vendor module's runtime import survives as its own module.
      expect(
        await readFile(join(output, "runtime", "shadow-stage.js"), "utf8"),
      ).toBeTruthy();
      expect(
        await readFile(join(output, "widgets", "lf-suggestion.js"), "utf8"),
      ).not.toContain("/runtime/widget-api.js");
    } finally {
      // Keep the build inputs until the operation finishes, even if the test times out.
      await rm(directory, { recursive: true });
    }
  }, 60_000);
});
