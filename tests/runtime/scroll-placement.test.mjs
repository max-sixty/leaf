import assert from "node:assert/strict";
import { test } from "node:test";
import { nearestScrollBy } from "../../skills/leaf/assets/runtime/rect.js";

test("nearest alignment keeps the visible end of an oversized destination", () => {
  assert.equal(nearestScrollBy(-400, 800, 52, 844), -44);
  assert.equal(nearestScrollBy(100, 1300, 52, 844), 48);
  assert.equal(nearestScrollBy(-400, 1300, 52, 844), 0);
});

test("nearest alignment reveals a short destination without moving one already shown", () => {
  assert.equal(nearestScrollBy(20, 80, 52, 844), -32);
  assert.equal(nearestScrollBy(800, 860, 52, 844), 16);
  assert.equal(nearestScrollBy(100, 160, 52, 844), 0);
});
