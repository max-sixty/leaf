/* What Undo says it took back for a widget's action: what the server reads the action
   as having done in its own document (`GestureWords.gesture`), worded with the widget's
   name on this page (records/undo.js, `actionWords`). */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "/runtime/state/semantic-state.js";
import { noticeReading } from "/runtime/transport/notifications.js";
import { createUndo } from "/runtime/records/undo.js";
import { servedState } from "../served.mjs";

const set = {
  kind: "action",
  widget: "detail",
  action: "set",
  revision: 1,
  attempt: "set-detail",
  id: "e1",
  seq: 1,
  ts: "2026-11-27T00:00:00Z",
};
const done = {
  ...set,
  widget: "route",
  action: "answer",
  attempt: "done-route",
  detail: {},
};
let taken = 0;
// A reading whose undo list holds `event`, read as `gesture`.
const reading = (event, gesture) =>
  servedState({
    taken: ++taken,
    browser: {
      basis: { through_seq: 1 },
      views: {
        1: {
          basis: { through_seq: 1 },
          undo: [{ event, newest: true, gesture }],
        },
      },
    },
  });

document.body.innerHTML =
  '<div id="detail" aria-label="Detail"></div><div id="route" aria-label="Which route?"></div>';
applicationState.setPhase("ready");
applicationState.identify(1);
const { withdraw } = createUndo({
  post: () => Promise.resolve({}),
  stateApplying: () => false,
  unaccountedGesture: () => false,
});
// What the notice says once Undo has taken back `event`, read as `gesture`.
const undone = async (event, gesture) => {
  applicationState.adopt(reading(event, gesture));
  await withdraw(event);
  return String(noticeReading().message);
};

test("Undo says the value an action set, and an empty one as cleared", async () => {
  const setTo = (value) =>
    undone({ ...set, detail: { value } }, { form: "set", value });
  assert.match(await setTo("7"), /^Undone: set “Detail” to “7” /);
  assert.match(await setTo(""), /^Undone: cleared “Detail” /);
});

test("Undo says what Done answered with, and an empty pick as only answered", async () => {
  const answered = (chosen) => undone(done, { form: "answer", chosen });
  assert.match(
    await answered(["Fast path", "Slow path"]),
    /^Undone: answered “Which route\?” with “Fast path”, “Slow path” /,
  );
  assert.match(await answered([]), /^Undone: answered “Which route\?” /);
});
