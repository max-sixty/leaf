/* Undo waits while a newer action has not yet been presented.

   A reading can log an action before or after the action's own POST answers. Until
   its document pass presents, a withdrawal of an earlier action could take back a
   gesture under a stale view. The ledger's lifecycle owns which states those are;
   this drives the one withdrawal door through both orders. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";
import { createUndo } from "/runtime/undo.js";

const spec = { unit: "widget" };
const action = (attempt, extra = {}) => ({
  kind: "action",
  widget: "choice",
  action: "decide",
  detail: {},
  revision: 1,
  attempt,
  ...extra,
});
const earlier = action("earlier", { id: "e0", seq: 1 });
const noAsks = () => ({ all: [], user: [], unanswered: [] });
let taken = 0;
// A reading whose log holds `events`, each standing and each the user's to take back.
const reading = (events) => ({
  taken: ++taken,
  layer: { generation: "test" },
  active: { revision: 1 },
  events,
  workflows: [],
  activity: null,
  browser: {
    basis: { through_seq: events.length },
    receipts: events,
    thread_memberships: {},
    todos: [],
    ended_todos: [],
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        thread: {
          threads: [],
          projection: { entries: [], actions: [], reports: [], desired: [] },
          asks: noAsks(),
        },
        coverage: [],
        undo: events.map((event) => ({ event })).reverse(),
        queues: { questions: [], tasks: [], done: [] },
        approval_blocking: [],
        document: {
          asks: noAsks(),
          projection: {
            entries: events.map((event) => ({
              event,
              coordinate: ["choice", "choice", "decide"],
              spec,
              scope: "page",
              value: "decide",
              restated: [],
              absorbed: false,
              stands: true,
            })),
            actions: events.map((event) => event.id),
            reports: [],
            desired: events.slice(-1).map((event) => event.id),
          },
        },
      },
    },
  },
});

test("Undo waits for a newer action through its send, answer and presentation", () => {
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: {
      "lf-choice": { "x-state": { decide: { ...spec, writer: "user" } } },
      $states: { "lf-choice": { decide: { writer: "user", definition: {} } } },
    },
    authored: new Map([
      [
        "choice",
        {
          tag: "lf-choice",
          specs: new Map([["decide", spec]]),
          positions: {},
          state: { decide: { action: null, value: null, detail: {} } },
        },
      ],
    ]),
    descriptors: new Map(),
  });
  applicationState.adopt(reading([earlier]));
  const posted = [];
  const { withdraw } = createUndo({
    post: (event) => {
      posted.push(event.undoes);
      return Promise.resolve(null);
    },
    stateApplying: () => false,
    unaccountedGesture: () => false,
  });
  const undoWaits = () => {
    const before = posted.length;
    return withdraw(earlier) === null && posted.length === before;
  };

  // A reading logs the new action before its POST answers.
  const polled = { ...action("polled"), id: "e1", seq: 2 };
  applicationState.enqueue(action("polled"), "now");
  assert.equal(applicationState.entry("polled").state, "sending");
  assert.equal(undoWaits(), true);
  applicationState.adopt(reading([earlier, polled]));
  assert.equal(applicationState.entry("polled").state, "sending:logged");
  assert.equal(undoWaits(), true);
  applicationState.present([earlier, polled]);
  assert.equal(undoWaits(), false);
  applicationState.accept("polled", polled);

  // The POST answers before a reading logs the next one. The user's later
  // accepted action is still only drawn locally, so an earlier Undo must wait.
  const answered = { ...action("answered"), id: "e2", seq: 3 };
  applicationState.enqueue(action("answered"), "now");
  applicationState.accept("answered", answered);
  assert.equal(applicationState.entry("answered").state, "accepted");
  assert.equal(undoWaits(), true);
  applicationState.adopt(reading([earlier, polled, answered]));
  assert.equal(applicationState.entry("answered").state, "accepted:logged");
  assert.equal(undoWaits(), true);
  applicationState.present([earlier, polled, answered]);
  assert.equal(undoWaits(), false);
});
