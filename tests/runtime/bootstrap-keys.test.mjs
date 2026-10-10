/* Bootstrap hands over real queued input without claiming native keys in an empty turn. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("an empty bootstrap handover preserves native Space", () => {
  const script = document.createElement("script");
  const descriptor = Object.getOwnPropertyDescriptor(document, "currentScript");
  Object.defineProperty(document, "currentScript", {
    value: script,
    configurable: true,
  });
  const root = document.documentElement;
  const keyboard = root.lfKeyboard;
  root.lfKeyboard = { quick: true };
  try {
    (0, eval)(
      readFileSync(
        new URL("../../skills/leaf/assets/runtime/bootstrap.js", import.meta.url),
        "utf8",
      ),
    );
    const detail = { ready: () => true, keep: () => true };
    document.dispatchEvent(new CustomEvent("lf-held-keys", { detail }));
    assert.equal(detail.keys, undefined);
    const space = new window.KeyboardEvent("keydown", {
      key: " ",
      bubbles: true,
      cancelable: true,
    });
    document.body.dispatchEvent(space);
    assert.equal(space.defaultPrevented, false);
    // A real pending command still transfers, and releases this startup's listeners.
    document.dispatchEvent(
      new CustomEvent("lf-held-keys", {
        detail: { ready: () => false, keep: () => true },
      }),
    );
    const key = new window.KeyboardEvent("keydown", {
      key: "x",
      bubbles: true,
      cancelable: true,
    });
    document.body.dispatchEvent(key);
    assert.equal(key.defaultPrevented, true);
    const queued = { ready: () => true, keep: () => false };
    document.dispatchEvent(new CustomEvent("lf-held-keys", { detail: queued }));
    assert.deepEqual(queued.keys, [key]);
    queued.release();
  } finally {
    root.lfKeyboard = keyboard;
    if (descriptor) Object.defineProperty(document, "currentScript", descriptor);
    else delete document.currentScript;
  }
});
