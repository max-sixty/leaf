/* The queue walk repaints the keys as On me empties or fills.

   The m/M row stands on On me, and Done on the to-dos it holds, so the walk watches
   the list the publication serves (`effective.queues.on_user`) and asks for the frame
   that repaints the keys when what it offers changes. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";
import { mountRepaint } from "/runtime/repaint.js";
import { nextRender } from "/runtime/rendering.js";
import { createQueueWalk } from "/runtime/queue-walk.js";

const noAsks = () => ({ all: [], user: [], unanswered: [] });
let taken = 0;
// A reading whose view lists `onUser` on the user's list, each a to-do the log holds open.
const reading = (onUser) => ({
  taken: ++taken,
  layer: { generation: "test" },
  active: { revision: 1 },
  events: [],
  files: {},
  workflows: [],
  activity: null,
  browser: {
    basis: { through_seq: 0 },
    receipts: [],
    thread_memberships: {},
    todos: onUser.map((item) => ({
      ...item,
      state: "open",
      ts: "2026-10-13T00:00:00Z",
      revision: 1,
      running: null,
      agent: null,
      session: null,
      outcome: null,
    })),
    ended_todos: [],
    version_notes: {},
    views: {
      1: {
        basis: { revision: 1, through_seq: 0 },
        thread: {
          threads: [],
          projection: { entries: [], actions: [], reports: [], desired: [] },
          asks: noAsks(),
        },
        coverage: [],
        undo: [],
        reports: [],
        queues: { on_user: onUser, on_agent: [], done: [] },
        approval_blocking: [],
        document: {
          asks: noAsks(),
          projection: { entries: [], actions: [], reports: [], desired: [] },
        },
      },
    },
  },
});
const todo = {
  kind: "todo",
  id: "t1",
  owner: "user",
  subject: { kind: "page" },
  thread: null,
  live: false,
  title: "Check the release",
};
const frame = () => new Promise((resolve) => nextRender(resolve));

test("a to-do arriving on On me repaints the keys", async () => {
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: { $states: {} },
    authored: new Map(),
    descriptors: new Map(),
  });
  applicationState.adopt(reading([]));
  let frames = 0;
  mountRepaint({ reflectFirstScopes: () => frames++ });
  createQueueWalk({}).mount();
  await frame();
  const before = frames;

  applicationState.adopt(reading([todo]));
  assert.equal(applicationState.read().effective.queues.on_user.length, 1);
  await frame();
  assert.ok(frames > before, "the keys repaint once On me holds the to-do");
});
