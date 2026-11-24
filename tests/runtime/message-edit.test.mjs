/* A discarded rewrite is a gesture of the user's that ⌘Z takes back while it is their
   newest, and Restore discarded edit takes back by name after that. */
import assert from "node:assert/strict";
import test from "node:test";
import * as editing from "/runtime/thread/message-edit.js";
import { createCompositionInputs } from "/runtime/composing/input.js";
import { clearDraft, loadDraft, rewriteContext, saveDraft } from "/runtime/drafts.js";
import { applicationState } from "/runtime/semantic-state.js";
import { noticeReading } from "/runtime/notifications.js";
import { createUndo } from "/runtime/undo.js";
import { createGoToSequence } from "/runtime/keyboard/go-to-sequence.js";
import { dispatchKey } from "/runtime/keyboard/dispatch.js";
import { servedState } from "../served.mjs";
import "/runtime/thread/landing.js";

applicationState.setPhase("ready");
const { wireInput } = createCompositionInputs({
  inputHint: () => null,
  uploadMedia: () => {
    throw new Error("No upload in this test");
  },
});

// A reading whose undo list holds `attempts`, newest first, each the user's to take
// back, as another tab's gestures reach this one.
let taken = 0;
const reading = (attempts) =>
  servedState({
    taken: ++taken,
    browser: {
      basis: { through_seq: attempts.length },
      views: {
        1: {
          basis: { through_seq: attempts.length },
          undo: attempts.map((attempt, at) => ({
            event: {
              kind: "action",
              widget: "choice",
              action: "decide",
              detail: {},
              revision: 1,
              attempt,
              id: `e${at}`,
              seq: attempts.length - at,
            },
            newest: at === 0,
          })),
        },
      },
    },
  });
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

test("⌘Z takes the newest discard back, and Restore discarded edit takes it by name", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  applicationState.adopt(reading(["older"]));
  discard("unchanged", "Original words");
  assert.equal(undo.restore.when(), false);

  discard("last", "  The last discarded rewrite\nwith its spacing.  ");
  const ctx = rewriteContext("last");
  assert.equal(takes().message, "Edit discarded");
  assert.equal(takes().press?.command, "history.undo");

  // An older gesture taken back by another route leaves the discard the newest.
  applicationState.adopt(reading([]));
  assert.equal(takes().press?.command, "history.undo");

  // A newer gesture, here another tab's, takes ⌘Z from it; the notice keeps its
  // words without a press, and Restore discarded edit still reaches it.
  applicationState.adopt(reading(["newer"]));
  assert.equal(takes().message, "Edit discarded");
  assert.equal(takes().press?.command, null);
  assert.equal(undo.restore.when(), true);

  // Words written since stay, after the ones coming back.
  saveDraft(ctx, "A newer draft");
  await undo.restore.run();
  assert.equal(
    loadDraft(ctx)?.text,
    "  The last discarded rewrite\nwith its spacing.  \n\nA newer draft",
  );
  assert.deepEqual(visits, [ctx]);
  assert.match(String(takes().message), /^Undone: discarded “/);
  assert.equal(undo.restore.when(), false);
  clearDraft(ctx);

  discard("again", "Taken back by ⌘Z");
  await undo.undoLast();
  assert.equal(loadDraft(rewriteContext("again"))?.text, "Taken back by ⌘Z");
  assert.deepEqual(loadDraft(rewriteContext("again"))?.payload, { over: "revision-1" });
  assert.deepEqual(visits, [ctx, rewriteContext("again")]);
  clearDraft(rewriteContext("again"));
});

test("g D restores the discarded rewrite", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  visits.length = 0;
  const door = { shows: () => false, press: () => {} };
  const goTo = createGoToSequence({
    doors: {
      threads: door,
      queue: door,
      agent: { ...door, name: () => "On Agent" },
      leaves: door,
    },
    hintChrome: { barriers: () => [] },
    directDestinations: () => [undo.restore],
    openPageMap: () => {},
    scrollToElement: () => {},
    leavesOffered: () => false,
    placeThreadEdge: () => {},
  });
  const press = (key, shiftKey = false) =>
    dispatchKey(
      new window.KeyboardEvent("keydown", { key, shiftKey, cancelable: true }),
    );
  discard("keyboard", "Recover by keyboard");
  assert.equal(press("g"), true);
  assert.equal(press("D", true), true);
  assert.equal(goTo.goToSequenceActive(), false);
  assert.equal(loadDraft(rewriteContext("keyboard"))?.text, "Recover by keyboard");
  assert.deepEqual(visits, [rewriteContext("keyboard")]);
});
