import assert from "node:assert/strict";
import { test } from "node:test";
import { maturePnpm } from "./mature-pnpm.mjs";

test("pnpm moves to the newest release old enough for minimumReleaseAge", () => {
  const now = Date.parse("2026-11-26T00:00:00Z");
  const time = {
    created: "2016-01-01T00:00:00Z",
    "1.9.0": "2026-11-01T00:00:00Z",
    "1.10.0": "2026-11-20T00:00:00Z",
    "2.0.0-rc.1": "2026-11-21T00:00:00Z",
    "1.11.0": "2026-11-24T00:00:00Z",
  };
  assert.equal(maturePnpm(time, 3 * 24 * 60, now), "1.10.0");
  assert.throws(() => maturePnpm(time, 60 * 24 * 60, now), /No pnpm release/);
});
