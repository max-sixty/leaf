/** TypeScript's checked value imports retain their module's initialization. */
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";
import { build } from "./esbuild.mjs";

test("checked value imports keep initialization when used only as types", async () => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-typed-import-"));
  try {
    await writeFile(
      path.join(scratch, "owner.ts"),
      'console.log("owner initialized"); export class Owner { value = 1; }',
    );
    const entry = path.join(scratch, "reader.ts");
    await writeFile(
      entry,
      'import { Owner } from "./owner.js"; export function read(owner: Owner) { return owner.value; }',
    );
    const config = path.join(scratch, "tsconfig.json");
    await writeFile(
      config,
      JSON.stringify({
        extends: fileURLToPath(
          new URL("../browser/types/tsconfig.json", import.meta.url),
        ),
        compilerOptions: { types: [] },
        include: ["reader.ts"],
      }),
    );
    const checked = spawnSync(
      process.execPath,
      [
        fileURLToPath(new URL("../node_modules/typescript/bin/tsc", import.meta.url)),
        "--project",
        config,
      ],
      { encoding: "utf8" },
    );
    assert.equal(checked.status, 0, checked.stdout + checked.stderr);
    const result = await build({
      entryPoints: [entry],
      bundle: true,
      format: "iife",
      target: "es2022",
      write: false,
    });
    const initialized = [];
    runInNewContext(result.outputFiles[0].text, {
      console: { log: (message) => initialized.push(message) },
    });
    assert.deepEqual(initialized, ["owner initialized"]);
  } finally {
    await rm(scratch, { recursive: true });
  }
});
