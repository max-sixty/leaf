import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
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
      for (const sub of ["runtime", "widgets", "page", "vendor"]) {
        await mkdir(join(layer, sub), { recursive: true });
      }
      await writeFile(
        join(layer, "leaf.js"),
        `import { state } from "${root}/page/state.js"; import { moduleUrl, prose } from "${root}/runtime/url.js"; console.log(state, moduleUrl, prose, import.meta.url);`,
      );
      await writeFile(
        join(layer, "runtime", "url.js"),
        'export const moduleUrl = import.meta . url; export const prose = "import.meta.url";',
      );
      for (const entry of ["layer-client", "media", "widget-api", "check-api"]) {
        await writeFile(
          join(layer, "runtime", `${entry}.js`),
          `export const revision = "${revision}";`,
        );
      }
      await writeFile(
        join(layer, "runtime", "check-api.js"),
        'export { moduleUrl, prose } from "./url.js"; export const ownUrl = import.meta.url;',
      );
      await writeFile(
        join(layer, "widgets", "lf-study.js"),
        `import { state } from "${root}/page/state.js"; import { html } from "../vendor/lit.js"; console.log(state, html);`,
      );
      await writeFile(
        join(layer, "page", "state.js"),
        `export const state = { revision: "${revision}" };`,
      );
      await writeFile(join(layer, "vendor", "lit.js"), "export const html = 1;\n");
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
      // Execute the emitted module so the check is independent of minifier syntax.
      const entry = pathToFileURL(join(layer, "runtime", "check-api.js")).href;
      const urls = JSON.parse(
        execFileSync(
          process.execPath,
          [
            "--input-type=module",
            "-e",
            `globalThis.location = {origin: "https://leaf.invalid"}; console.log(JSON.stringify(await import(${JSON.stringify(entry)})));`,
          ],
          { encoding: "utf8" },
        ),
      );
      expect(urls).toEqual({
        ownUrl: `https://leaf.invalid${root}/runtime/check-api.js`,
        moduleUrl: `https://leaf.invalid${root}/runtime/url.js`,
        prose: "import.meta.url",
      });
      // A relative import of a vendor module keeps the page's one copy.
      expect(await readFile(join(layer, "widgets", "lf-study.js"), "utf8")).toContain(
        `from"${root}/vendor/lit.js"`,
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
      // The production layer is a page's bundled packages beside the runtime a
      // prepared installation serves, as the live shell publishes a revision.
      const install = join(directory, "install");
      execFileSync("uv", ["run", "leaf-dev", "distribution", "--output", install], {
        cwd: fileURLToPath(new URL("../..", import.meta.url)),
      });
      const runtime = join(directory, "layer");
      execFileSync(join(install, "bin", "leaf"), ["page", "init", runtime], {
        env: { ...process.env, XDG_STATE_HOME: join(directory, "state") },
      });
      execFileSync(
        "uv",
        [
          "run",
          "--quiet",
          "--no-dev",
          "--project",
          install,
          "python",
          "-c",
          [
            "import sys",
            "from pathlib import Path",
            "from leaf.runtime_selection import serving_runtime",
            "for path, resource in serving_runtime().resources({}).items():",
            "    target = Path(sys.argv[1]) / path.lstrip('/')",
            "    target.parent.mkdir(parents=True, exist_ok=True)",
            "    target.write_bytes(resource.data)",
          ].join("\n"),
          runtime,
        ],
        { env: { ...process.env, XDG_STATE_HOME: join(directory, "state") } },
      );

      const output = join(directory, "bundled");
      await bundleLayer(runtime, "/published/layer", output);
      const bundled = await readFile(join(output, "leaf.js"), "utf8");
      expect(await readFile(join(output, "runtime", "media.js"), "utf8")).toBeTruthy();
      expect(
        await readFile(join(output, "runtime", "layer-client.js"), "utf8"),
      ).toBeTruthy();
      const verifier = await readFile(
        fileURLToPath(
          new URL(
            "../../dev/leaf_dev/commands/verify_site_browser.js",
            import.meta.url,
          ),
        ),
        "utf8",
      );
      for (const [, name] of verifier.matchAll(/runtimeModule\("([^"]+)"\)/g)) {
        expect(
          await readFile(join(output, "runtime", `${name}.js`), "utf8"),
          `the browser verifier imports bundled runtime/${name}.js`,
        ).toBeTruthy();
      }
      expect(bundled).not.toMatch(/from"\.\/runtime\/(?!bundle-)/);
      // The kernel holds the framework; the page still shares one Lit, which the
      // revision's import map sends to its own vendor directory.
      const kernel = (
        await Promise.all(
          (await readdir(join(output, "runtime")))
            .filter((file) => file.endsWith(".js"))
            .map((file) => readFile(join(output, "runtime", file), "utf8")),
        )
      ).join("\n");
      expect(kernel).toContain('"accepted:presented"');
      expect(kernel).toContain('from"/vendor/lit.js"');
      expect(kernel).not.toContain("litHtmlVersions");
      expect(kernel).not.toContain("/vendor/signals-core.js");
      // A widget's runtime imports are compiled chunks, never the public module URL.
      // The compiled widget-api.js entry can be one of them, holding modules the
      // compiler merged into it.
      expect(
        await readFile(join(output, "widgets", "lf-suggestion.js"), "utf8"),
      ).not.toMatch(/"(?:\/published\/layer)?\/runtime\//);
    } finally {
      // Keep the build inputs until the operation finishes, even if the test times out.
      await rm(directory, { recursive: true });
    }
  }, 60_000);
});
