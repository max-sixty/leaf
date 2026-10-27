/* Discarded rewrites belong to this tab until restored into the ordinary draft. */
import assert from "node:assert/strict";
import test from "node:test";
import * as editing from "/runtime/thread/message-edit.js";
import { createCompositionInputs } from "/runtime/composing/input.js";
import {
  clearDraft,
  loadDraft,
  loadDraftPayload,
  rewriteContext,
  saveDraft,
} from "/runtime/drafts.js";
import { applicationState } from "/runtime/semantic-state.js";
import { draftStore } from "/runtime/storage.js";
import { createGoToSequence } from "/runtime/keyboard/go-to-sequence.js";
import { dispatchKey } from "/runtime/keyboard/dispatch.js";
import "/runtime/thread/landing.js";

applicationState.setPhase("ready");
const { wireInput } = createCompositionInputs({
  inputHint: () => null,
  uploadMedia: () => {
    throw new Error("No upload in this test");
  },
});

function discard(id, text, said = "Original words") {
  const editor = new editing.MessageEditor(
    id,
    {},
    {
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
    },
  );
  editor.input.value = text;
  editor.input.dispatchEvent(new Event("input", { bubbles: true }));
  editor.node.querySelector(".lf-msg-edit-cancel").click();
  editor.dispose();
  assert.equal(loadDraft(rewriteContext(id)), null);
}

test("restore keeps the latest changed rewrite and its revision, without replacing newer work", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  discard("first", "An older discarded rewrite");
  discard("last", "  The last discarded rewrite\nwith its spacing.  ");
  discard("unchanged", "Original words");
  discard("empty", "");
  const visits = [];
  let present = true;
  const restore = editing.createRewriteRestore({
    holdsThreadDraft: () => present,
    revealInThread: async (ctx) => {
      visits.push(ctx);
    },
  });
  const ctx = rewriteContext("last");
  assert.equal(restore.when(), true);
  present = false;
  assert.equal(restore.when(), false);
  present = true;
  saveDraft(ctx, "A newer draft");
  assert.equal(restore.when(), false);
  await restore.run();
  assert.equal(loadDraft(ctx), "A newer draft");
  assert.deepEqual(visits, []);
  clearDraft(ctx);
  // Another tab writes before its storage event reaches this one. The cached
  // tombstone must not authorize replacing those newer words.
  saveDraft("other-tab", "Words from another tab", { over: "revision-2" });
  draftStore.set("lf-draft:" + ctx, draftStore.get("lf-draft:other-tab"));
  await restore.run();
  assert.equal(loadDraft(ctx), "Words from another tab");
  assert.deepEqual(visits, []);
  clearDraft(ctx);
  await restore.run();
  assert.equal(loadDraft(ctx), "  The last discarded rewrite\nwith its spacing.  ");
  assert.deepEqual(loadDraftPayload(ctx), { over: "revision-1" });
  assert.deepEqual(visits, [ctx]);
  assert.equal(restore.when(), false);
  await restore.run();
  assert.deepEqual(visits, [ctx]);
});

test("g D restores the discarded rewrite", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const visits = [];
  const restore = editing.createRewriteRestore({
    holdsThreadDraft: () => true,
    revealInThread: async (ctx) => visits.push(ctx),
  });
  const door = { shows: () => false, press: () => {} };
  const goTo = createGoToSequence({
    doors: { threads: door, queue: door, leaves: door },
    hintChrome: { barriers: () => [] },
    directDestinations: () => [restore],
    openPageMap: () => {},
    scrollToElement: () => {},
    leavesOffered: () => false,
    glideTo: () => {},
    placeThreadEdge: () => {},
    stopGlide: () => {},
  });
  const press = (key, shiftKey = false) =>
    dispatchKey(
      new window.KeyboardEvent("keydown", { key, shiftKey, cancelable: true }),
    );
  discard("keyboard", "Recover by keyboard");
  assert.equal(press("g"), true);
  assert.equal(press("D", true), true);
  assert.equal(goTo.goToSequenceActive(), false);
  assert.equal(loadDraft(rewriteContext("keyboard")), "Recover by keyboard");
  assert.deepEqual(visits, [rewriteContext("keyboard")]);
});
