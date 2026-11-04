/* The queue walk repaints the keys as On me empties or fills.

   The m/M row stands on On me, and Done on the to-dos it holds, so the walk watches
   the queues the publication serves (`readQueues`) and asks for the frame that
   repaints the keys when what it offers changes. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";
import { mountRepaint } from "/runtime/repaint.js";
import { nextRender } from "/runtime/rendering.js";
import { createQueueWalk } from "/runtime/queue-walk.js";
import { servedReading, servedState } from "../served.mjs";

// A page with nothing on On me, then the same page once the agent put a to-do there.
const empty = servedState();
const filled = servedReading("user to-do");
const frame = () => new Promise((resolve) => nextRender(resolve));

test("a to-do arriving on On me repaints the keys", async () => {
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: { $states: {} },
    authored: new Map(),
    descriptors: new Map(),
  });
  applicationState.adopt(empty);
  let frames = 0;
  mountRepaint({ reflectFirstScopes: () => frames++ });
  createQueueWalk({}).mount();
  await frame();
  const before = frames;

  applicationState.adopt(filled);
  assert.equal(applicationState.read().effective.queues.on_user.length, 1);
  // The walk's watcher reads the queues on the microtask after the publication.
  await null;
  await frame();
  assert.ok(frames > before, "the keys repaint once On me holds the to-do");
});
