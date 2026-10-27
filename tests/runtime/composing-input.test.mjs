/* Generated composer controls follow shared readings without replacing the editor.
 * The native textarea stands in for leaf-text's textarea contract: CodeMirror and
 * browser geometry are exercised by the existing composer browser journeys. */
import assert from "node:assert/strict";
import test from "node:test";
import { signal } from "/runtime/framework.js";
import { createCompositionInputs, syncInput } from "/runtime/composing/input.js";
import { raiseError } from "/runtime/errors.js";
import { focusDestination } from "/runtime/focus.js";

function composer(t, options = {}, owner = null) {
  const row = document.createElement("div");
  const input = document.createElement("textarea");
  input.restartHistory = () => {};
  input.checkVisibility = () => true;
  input.value = "Kept words";
  row.append(input);
  document.body.append(row);
  const inputs =
    owner ??
    createCompositionInputs({
      uploadMedia: () => {},
      inputHint: () => null,
    });
  const sync = inputs.wireInput(input, {
    hint: "Comment",
    sends: "send",
    save: () => {},
    send: () => {},
    ...options,
  });
  const field = row.querySelector("leaf-composition-field");
  t.after(() => row.remove());
  return { row, input, sync, field, button: sync.button };
}

test("composer chrome reacts to errors and availability while preserving the editor and controls", async (t) => {
  const busy = signal(false);
  const { row, input, field, sync, button } = composer(t, { busy: () => busy.value });
  input.setSelectionRange(2, 6);
  const cover = row.querySelector(".lf-compose-error");
  assert.equal(button.getAttribute("aria-disabled"), "false");
  busy.value = true;
  await field.updateComplete;
  assert.equal(button.getAttribute("aria-disabled"), "true");
  busy.value = false;
  await field.updateComplete;
  const failure = raiseError("Please review these words", {
    subject: input,
    announce: false,
  });
  await field.updateComplete;
  assert.equal(cover.hidden, false);
  assert.equal(cover.textContent.trim(), "Please review these words");
  assert.equal(button.getAttribute("aria-disabled"), "true");
  failure.clear();
  await field.updateComplete;
  assert.equal(cover.hidden, true);
  assert.equal(button.getAttribute("aria-disabled"), "false");
  sync.load("Kept words");
  await field.updateComplete;
  assert.equal(row.querySelector("textarea"), input);
  assert.equal(row.querySelector(".lf-compose-submit"), button);
  assert.equal(input.value, "Kept words");
  assert.equal(input.selectionStart, 2);
  assert.equal(input.selectionEnd, 6);
});

test("focus, contextual hints and errors leave unrelated composition readings alone", async (t) => {
  let hinted = null;
  const owner = createCompositionInputs({
    uploadMedia: () => {},
    inputHint: () => hinted,
  });
  const reads = [0, 0, 0];
  const fields = reads.map((_, index) =>
    composer(
      t,
      {
        hint: () => {
          reads[index]++;
          return `Comment ${index}`;
        },
      },
      owner,
    ),
  );
  const settled = () => Promise.all(fields.map(({ field }) => field.updateComplete));
  await settled();
  const before = [...reads];
  hinted = { box: fields[0].input, label: "c" };
  owner.publishInputHint();
  await settled();
  assert.equal(fields[0].input.placeholder, "Comment 0 c");
  assert.deepEqual(reads, [before[0] + 1, before[1], before[2]]);
  focusDestination(fields[1].input, "move");
  await settled();
  assert.match(fields[1].input.placeholder, /⏎/);
  assert.deepEqual(reads, [before[0] + 1, before[1] + 1, before[2]]);
  const failure = raiseError("Read these words", {
    subject: fields[1].input,
    announce: false,
  });
  await settled();
  assert.equal(fields[1].button.getAttribute("aria-disabled"), "true");
  assert.deepEqual(reads, [before[0] + 1, before[1] + 2, before[2]]);
  fields[1].input.checkVisibility = () => false;
  syncInput(fields[1].input);
  await settled();
  assert.equal(fields[1].row.querySelector(".lf-compose-error").hidden, true);
  assert.equal(fields[1].button.getAttribute("aria-disabled"), "false");
  assert.equal(reads[0], before[0] + 1);
  assert.equal(reads[2], before[2]);
  failure.clear();
});

test("dictation and send trade the same field seat as its draft changes", async (t) => {
  const previous = globalThis.SpeechRecognition;
  globalThis.SpeechRecognition = class {};
  t.after(() => {
    globalThis.SpeechRecognition = previous;
  });
  const { row, input, field, sync, button } = composer(t);
  const microphone = row.querySelector(".lf-compose-dictate");
  assert.equal(microphone.hidden, true);
  assert.equal(button.hidden, false);
  sync.load("");
  await field.updateComplete;
  assert.equal(microphone.hidden, false);
  assert.equal(button.hidden, true);
  assert.equal(
    field.querySelector(".lf-compose-field").hasAttribute("data-words"),
    false,
  );
  input.value = "A new thought";
  input.dispatchEvent(new Event("input"));
  await field.updateComplete;
  assert.equal(microphone.hidden, true);
  assert.equal(button.hidden, false);
  assert.equal(
    field.querySelector(".lf-compose-field").hasAttribute("data-words"),
    true,
  );
});

test("a rewrite's generated save control shares its action row with retained discard", async (t) => {
  const actions = document.createElement("span");
  const discard = document.createElement("button");
  discard.textContent = "Discard";
  actions.append(discard);
  document.body.append(actions);
  t.after(() => actions.remove());
  const { input, field, sync, button } = composer(t, {
    submitIn: actions,
    sendClass: "lf-msg-control lf-msg-edit-save",
    sends: "save",
    icon: "save",
  });
  assert.equal(actions.querySelector(".lf-msg-edit-save"), button);
  assert.equal(actions.firstElementChild, discard);
  assert.equal(button.getAttribute("aria-label"), "Save");
  sync.load("");
  await field.updateComplete;
  assert.equal(button.getAttribute("aria-disabled"), "true");
  assert.equal(actions.querySelector(".lf-msg-edit-save"), button);
  assert.equal(field.querySelector("textarea"), input);
  assert.equal(actions.firstElementChild, discard);
});

test("a send settling after the field leaves does not resubscribe the detached view", async (t) => {
  const busy = signal(false);
  let reads = 0;
  const { row, input, field, button } = composer(t, {
    busy: () => {
      reads++;
      return busy.value;
    },
  });
  await field.updateComplete;
  row.remove();
  syncInput(input);
  await field.updateComplete;
  const before = reads;
  busy.value = true;
  await field.updateComplete;
  assert.equal(reads, before);
  document.body.append(row);
  await field.updateComplete;
  assert.equal(button.getAttribute("aria-disabled"), "true");
});
