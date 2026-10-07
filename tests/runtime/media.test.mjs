/* A composer's media projection removes only the suffix its writer appended. */
import assert from "node:assert/strict";
import test from "node:test";

import { readPastedMedia, writePastedMedia } from "/runtime/media.js";

test("a stored draft preserves its exact text through the pasted-media projection", () => {
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
      const written = writePastedMedia(text, paths);
      const read = readPastedMedia(written);
      assert.deepEqual(read, { text, paths }, JSON.stringify({ text, paths }));
      assert.equal(writePastedMedia(read.text, read.paths), written);
    }
  const inline =
    "An authored image ![Pasted image](/media/051bee487bfb5d13.png) stays here.";
  assert.deepEqual(readPastedMedia(inline), { text: inline, paths: [] });
});
