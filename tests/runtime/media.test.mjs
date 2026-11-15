/* A composer's media projection removes only the suffix its writer appended, and an
   image link pressed before startup seats the viewer keeps its own destination. */
import assert from "node:assert/strict";
import test from "node:test";

import { mediaViewer, readAttachedMedia, writeAttachedMedia } from "/runtime/media.js";

test("a stored draft preserves its exact text through the attached-media projection", () => {
  const images = ["/media/051bee487bfb5d13.png", "/media/aaaaaaaaaaaaaaaa.png"];
  for (const text of [
    "",
    "First line",
    "\nFirst line\n",
    "First line\n\n\n\n",
    "\n\n",
    "First\n\n\n\nLast",
  ])
    for (const paths of [[], images.slice(0, 1), images]) {
      const written = writeAttachedMedia(text, paths);
      const read = readAttachedMedia(written);
      assert.deepEqual(read, { text, paths }, JSON.stringify({ text, paths }));
      assert.equal(writeAttachedMedia(read.text, read.paths), written);
    }
  const inline =
    "An authored image ![Attached image](/media/051bee487bfb5d13.png) stays here.";
  assert.deepEqual(readAttachedMedia(inline), { text: inline, paths: [] });
});

test("an image link pressed before the viewer has a home keeps its own destination", () => {
  // Startup attaches the viewer to the chrome after the module registers its press
  // handler; a press between the two follows the link rather than opening nothing.
  assert.equal(mediaViewer.isConnected, false);
  const link = document.createElement("a");
  link.href = "/media/051bee487bfb5d13.png";
  const image = document.createElement("img");
  image.src = link.href;
  link.append(image);
  document.body.append(link);
  const press = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
  /** @type {unknown[]} */
  const errors = [];
  const report = (/** @type {ErrorEvent} */ event) => errors.push(event.error);
  window.addEventListener("error", report);
  try {
    link.dispatchEvent(press);
  } finally {
    window.removeEventListener("error", report);
    link.remove();
  }
  assert.deepEqual(errors, []);
  assert.equal(press.defaultPrevented, false);
  assert.equal(mediaViewer.open, false);
});
