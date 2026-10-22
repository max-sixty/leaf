import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { threadCounts } from "../../browser/runtime/thread/model.js";

// `tests/model/test_thread_counts.py` reads the same cases against the served row's
// `thread_counts`, so the panel's marks and Claude Code's band count alike.
const cases = JSON.parse(
  readFileSync(new URL("../thread_count_cases.json", import.meta.url)),
);

for (const { name, threads, counts } of cases) {
  test(`the panel counts threads: ${name}`, () => {
    assert.deepEqual(threadCounts(threads), counts);
  });
}
