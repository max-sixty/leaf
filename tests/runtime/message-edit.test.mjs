/* A discarded rewrite is a gesture of the user's that ⌘Z takes back while it is their
   newest: after a newer gesture, once that one is taken back. */
import assert from "node:assert/strict";
import test from "node:test";
import * as editing from "/runtime/records/thread/message-edit.js";
import { createCompositionInputs } from "/runtime/annotations/composing/input.js";
import {
  clearDraft,
  loadDraft,
  rewriteContext,
  saveDraft,
} from "/runtime/records/drafts.js";
import { applicationState } from "/runtime/state/semantic-state.js";
import { noticeReading } from "/runtime/transport/notifications.js";
import { createUndo } from "/runtime/records/undo.js";
import { servedState } from "../served.mjs";
import "/runtime/records/thread/landing.js";

applicationState.setPhase("ready");
const { wireInput } = createCompositionInputs({
  inputHint: () => null,
  uploadMedia: () => {
    throw new Error("No upload in this test");
  },
});

// A reading whose undo list holds `attempts`, newest first, each the user's to take
// back, as another tab's gestures reach this one. Each gesture keeps the place in the
// log it was first given, and the reading has read through the latest.
let taken = 0;
const logged = new Map();
const reading = (attempts) => {
  for (const attempt of [...attempts].reverse())
    if (!logged.has(attempt)) logged.set(attempt, logged.size + 1);
  return servedState({
    taken: ++taken,
    browser: {
      basis: { through_seq: logged.size },
      views: {
        1: {
          basis: { through_seq: logged.size },
          undo: attempts.map((attempt, at) => ({
            event: {
              kind: "action",
              widget: "choice",
              action: "decide",
              detail: {},
              revision: 1,
              attempt,
              id: `e${logged.get(attempt)}`,
              seq: logged.get(attempt),
            },
            newest: at === 0,
          })),
        },
      },
    },
  });
};
applicationState.identify(1);

const visits = [];
const undo = createUndo({
  post: () => {
    throw new Error("A discard never reaches the log");
  },
  stateApplying: () => false,
  unaccountedGesture: () => false,
  resumeDraft: async (ctx) => {
    visits.push(ctx);
  },
});
const takes = () => noticeReading();

function discard(id, text, said = "Original words") {
  const editor = new editing.MessageEditor(id, {
    wireInput,
    said: () => said,
    base: () => "revision-1",
    send: () => {
      throw new Error("Discard must not send");
    },
    land: () => {},
    paint: () => {},
    previous: () => null,
    reveal: () => {},
  });
  editor.input.value = text;
  editor.input.dispatchEvent(new Event("input", { bubbles: true }));
  editor.actions.querySelector(".lf-msg-edit-cancel").click();
  editor.dispose();
  assert.equal(loadDraft(rewriteContext(id)), null);
}

test("⌘Z takes a discard back while it is the newest gesture", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  applicationState.adopt(reading(["older"]));
  discard("unchanged", "Original words");
  assert.notEqual(takes().message, "Edit discarded");

  discard("last", "  The last discarded rewrite\nwith its spacing.  ");
  const ctx = rewriteContext("last");
  assert.equal(takes().message, "Edit discarded");
  assert.equal(takes().press?.command, "history.undo");

  // An older gesture taken back by another route leaves the discard the newest.
  applicationState.adopt(reading([]));
  assert.equal(takes().press?.command, "history.undo");

  // A newer gesture, here another tab's, takes ⌘Z from it, and the notice keeps its
  // words without a press. Once that gesture is taken back, the discard is the newest
  // again.
  applicationState.adopt(reading(["newer"]));
  assert.equal(takes().message, "Edit discarded");
  assert.equal(takes().press?.command, null);
  applicationState.adopt(reading([]));
  assert.equal(takes().press?.command, "history.undo");

  // Words written since stay, after the ones coming back.
  saveDraft(ctx, "A newer draft");
  await undo.undoLast();
  assert.equal(
    loadDraft(ctx)?.text,
    "  The last discarded rewrite\nwith its spacing.  \n\nA newer draft",
  );
  assert.deepEqual(visits, [ctx]);
  assert.match(String(takes().message), /^Undone: discarded an edit of a message /);
  clearDraft(ctx);

  discard("again", "Taken back with its revision");
  await undo.undoLast();
  assert.equal(
    loadDraft(rewriteContext("again"))?.text,
    "Taken back with its revision",
  );
  assert.deepEqual(loadDraft(rewriteContext("again"))?.payload, { over: "revision-1" });
  assert.deepEqual(visits, [ctx, rewriteContext("again")]);
  clearDraft(rewriteContext("again"));
});

test("a discard made while no undo list is held is ordered once the list arrives", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  applicationState.identify(1);
  applicationState.adopt(reading(["older"]));
  // The page shows a revision its reading holds no view of, so it holds no list.
  applicationState.identify(2);
  discard("between", "Discarded between versions");
  applicationState.identify(1);
  assert.equal(takes().press?.command, "history.undo");
  applicationState.adopt(reading(["later", "older"]));
  assert.equal(takes().press?.command, null);
  clearDraft(rewriteContext("between"));
});
