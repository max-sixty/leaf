import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import { bundleLayer } from "../bundle-runtime.mjs";

const temporary: string[] = [];

afterEach(async () => {
  await Promise.all(temporary.splice(0).map((path) => rm(path, { recursive: true })));
});

describe("published runtime bundle", () => {
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
    expect(bundled).not.toMatch(/from"\.\/runtime\/(?!bundle-)/);
    expect(
      await readFile(join(directory, "widgets", "lf-suggestion.js"), "utf8"),
    ).not.toContain("/runtime/widget-api.js");
  });
});
