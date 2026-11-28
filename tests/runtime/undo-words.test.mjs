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

test("Undo says the value an action set, and an empty one as cleared", async () => {
  document.body.innerHTML = '<div id="detail" aria-label="Detail"></div>';
  applicationState.setPhase("ready");
  applicationState.identify(1);
  const { withdraw } = createUndo({
    post: () => Promise.resolve({}),
    stateApplying: () => false,
    unaccountedGesture: () => false,
  });
  const undone = async (value) => {
    const event = { ...set, detail: { value } };
    applicationState.adopt(reading(event, { form: "set", value }));
    await withdraw(event);
    return String(noticeReading().message);
  };

  assert.match(await undone("7"), /^Undone: set “Detail” to “7” /);
  assert.match(await undone(""), /^Undone: cleared “Detail” /);
});
