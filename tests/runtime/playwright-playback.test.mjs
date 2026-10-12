import assert from "node:assert/strict";
import test from "node:test";
import {
  advancePlayback,
  mergeIntervals,
} from "../../skills/leaf/packages/playwright/widgets/playback.js";

test("recorded pace keeps the native clock", () => {
  assert.equal(advancePlayback(1000, 250), 1250);
});

test("review pace cannot jump over an important interval on a slow frame", () => {
  const windows = mergeIntervals([
    [1000, 2000],
    [1800, 2500],
    [4000, 4500],
  ]);
  assert.deepEqual(windows, [
    [1000, 2500],
    [4000, 4500],
  ]);
  // 100 wall ms reaches the interval; the remaining 200 ms runs at 0.35x.
  assert.equal(advancePlayback(700, 300, windows), 1070);
  // Crossing out of slow motion resumes the faster quiet interval exactly.
  assert.equal(advancePlayback(2465, 200, windows), 2800);
});

test("review result does not depend on animation frame partitioning", () => {
  const windows = [
    [200, 400],
    [450, 700],
  ];
  const oneFrame = advancePlayback(0, 2000, windows);
  let manyFrames = 0;
  for (let index = 0; index < 200; index++)
    manyFrames = advancePlayback(manyFrames, 10, windows);
  assert.ok(Math.abs(oneFrame - manyFrames) < 0.000001);
});
