/** Bundles use caller options without inheriting ambient compiler settings. */
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { runInNewContext } from "node:vm";
import test from "node:test";
import { build } from "./esbuild.mjs";

test("JavaScript imports keep initialization and ignore ambient emit settings", async () => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-build-config-"));
  try {
    await writeFile(
      path.join(scratch, "owner.js"),
      'console.log("owner initialized"); export class Owner { value = 1; }',
    );
    const entry = path.join(scratch, "reader.js");
    await writeFile(
      entry,
      'import { Owner } from "./owner.js"; /** @param {Owner} owner */ export function read(owner) { return owner.value; }',
    );
    const config = path.join(scratch, "tsconfig.json");
    await writeFile(
      config,
      JSON.stringify({ compilerOptions: { alwaysStrict: true } }),
    );
    const result = await build({
      entryPoints: [entry],
      bundle: true,
      format: "iife",
      target: "es2022",
      write: false,
    });
    assert.doesNotMatch(result.outputFiles[0].text, /["']use strict["']/);
    const initialized = [];
    runInNewContext(result.outputFiles[0].text, {
      console: { log: (message) => initialized.push(message) },
    });
    assert.deepEqual(initialized, ["owner initialized"]);
  } finally {
    await rm(scratch, { recursive: true });
  }
});
