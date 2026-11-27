import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { compile, compiledModules, typescriptOutputs } from "./typescript.mjs";

test("a module compiles to its code without types, comments kept", async () => {
  const source = [
    "/* The module's header. */",
    'import type { Count } from "./count.js";',
    'import { read } from "/runtime/widget-api.js";',
    "",
    "// The total of `counts`.",
    "export function total(counts: readonly Count[]): number {",
    "  return counts.reduce((sum, count) => sum + (count.value as number), 0);",
    "}",
    "",
    "export class Cache<K extends object> {",
    "  #held = new WeakMap<K, number>();",
    "  get(key: K): number | undefined {",
    "    return this.#held.get(key) ?? read(key)!;",
    "  }",
    "}",
    "",
  ].join("\n");
  assert.equal(
    await compile(source, "browser/runtime/lib/total.ts"),
    [
      "// Compiled from total.ts by build/typescript.mjs; edit that file.",
      "/* The module's header. */",
      "",
      'import { read } from "/runtime/widget-api.js";',
      "",
      "// The total of `counts`.",
      "export function total(counts) {",
      "  return counts.reduce((sum, count) => sum + count.value, 0);",
      "}",
      "",
      "export class Cache {",
      "  #held = new WeakMap();",
      "  get(key) {",
      "    return this.#held.get(key) ?? read(key);",
      "  }",
      "}",
      "",
    ].join("\n"),
  );
});

test("syntax that doesn't erase is refused", async () => {
  await assert.rejects(compile("enum Side { Left }\n", "browser/runtime/side.ts"));
});

test("each module's output stands beside it, and stays marked compiled once its module is gone", async (context) => {
  const scratch = await mkdtemp(path.join(tmpdir(), "leaf-typescript-"));
  context.after(() => rm(scratch, { recursive: true }));
  const put = async (name, text) => {
    await mkdir(path.dirname(path.join(scratch, name)), { recursive: true });
    await writeFile(path.join(scratch, name), text);
  };
  await put("browser/runtime/one.ts", "export const one: number = 1;\n");
  await put("browser/types/declared.d.ts", "export type Declared = 1;\n");
  await put("packages/demo/widgets/lf-demo.js", "export const handWritten = 1;\n");
  const outputs = await typescriptOutputs(scratch);
  assert.deepEqual([...outputs.keys()], ["browser/runtime/one.js"]);
  for (const [name, bytes] of outputs) await put(name, bytes);
  await rm(path.join(scratch, "browser/runtime/one.ts"));
  assert.deepEqual(await compiledModules(scratch), ["browser/runtime/one.js"]);
  assert.deepEqual((await typescriptOutputs(scratch)).size, 0);
});
