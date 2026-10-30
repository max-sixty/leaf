/* Authored margin content layout is inert until boot opens it and owns no annotation geometry. */
import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

test("import and a closed readDocumentHeaders schedule start no document layout owner", async () => {
  const loaded = [];
  const modules = registerHooks({
    load(url, context, next) {
      loaded.push(url);
      return next(url, context);
    },
  });
  let frames = 0;
  const frame = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = (...args) => {
    frames += 1;
    return frame(...args);
  };
  try {
    const owner = await import("/runtime/content-layout.js");
    const before = frames;
    owner.scheduleDocumentLayout();
    assert.equal(frames, before);
    assert.deepEqual(
      loaded.filter(
        (url) =>
          url.includes("/annotation-overlay/") || url.endsWith("/page-map-dialog.js"),
      ),
      [],
    );
  } finally {
    globalThis.requestAnimationFrame = frame;
    modules.deregister();
  }
});

test("an opened readDocumentHeaders completes unchanged readings with no main", async () => {
  const owner = await import("/runtime/content-layout.js");
  assert.equal(document.querySelector("main"), null);
  const completed = [];
  owner.openDocumentLayout({ onRead: (changed) => completed.push(changed) });
  assert.deepEqual(completed, [false]);
  owner.settleDocumentLayout();
  assert.deepEqual(completed, [false, false]);
});
