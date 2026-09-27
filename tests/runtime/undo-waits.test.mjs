/* Undo waits while an action the log holds is not yet on the page.

   A reading can log an action before or after the action's own POST answers. Either
   way the semantic root already draws the log's event while the page may still show
   what came before it, so an Undo that would take back an earlier gesture waits for
   that reading to be presented. The ledger's lifecycle owns which states those are;
   this drives the one withdrawal door through both orders. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";
import { createProjectionCommands } from "/runtime/projection/commands.js";

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
    thread: {
      threads: [],
      projection: { entries: [], actions: [], reports: [], desired: [] },
      asks: noAsks(),
    },
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        coverage: [],
        undo: events.map((event) => ({ event })).reverse(),
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

test("Undo waits while a logged action is unpresented, whichever answer came first", () => {
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: { "lf-choice": { "x-state": { decide: { ...spec, writer: "user" } } } },
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
  const { withdraw } = createProjectionCommands({
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
  applicationState.adopt(reading([earlier, polled]));
  assert.equal(applicationState.entry("polled").state, "sending:logged");
  assert.equal(undoWaits(), true);
  applicationState.present([earlier, polled]);
  assert.equal(undoWaits(), false);
  applicationState.accept("polled", polled);

  // The POST answers before a reading logs the next one.
  const answered = { ...action("answered"), id: "e2", seq: 3 };
  applicationState.enqueue(action("answered"), "now");
  applicationState.accept("answered", answered);
  applicationState.adopt(reading([earlier, polled, answered]));
  assert.equal(applicationState.entry("answered").state, "accepted:logged");
  assert.equal(undoWaits(), true);
  applicationState.present([earlier, polled, answered]);
  assert.equal(undoWaits(), false);
});
