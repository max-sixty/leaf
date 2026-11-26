/* A Markdown file's reading for its preview (lib/markdown.js, `markdownFileFragment`)
   writes the host's links and pictures after the rendering, so a host that moves a
   picture into an element of its own, as a Leaf page does with its media, gets that
   element in the picture's place. */
import assert from "node:assert/strict";
import test from "node:test";

import { loadMarkdown, markdownFileFragment } from "/runtime/lib/markdown.js";

test("a host's picture stands where the file's picture stood", async () => {
  assert.equal(await loadMarkdown(), true);
  const fragment = await markdownFileFragment("Before ![Chart](chart.png) after.", {
    picture: (image) => {
      const press = image.ownerDocument.createElement("button");
      press.append(image);
      return press;
    },
  });
  assert.equal(
    fragment.firstElementChild?.innerHTML,
    'Before <button><img src="chart.png" alt="Chart"></button> after.',
  );
});
