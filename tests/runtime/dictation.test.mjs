import assert from "node:assert/strict";
import test from "node:test";

import { createDictation } from "/runtime/composing/dictation.js";

/**
 * Native speech recognition needs microphone permission and a remote service.
 * This stand-in replaces only that boundary: the controller receives the native
 * callback shapes, while the draft and its ordinary input callback remain real.
 */
function composer(initial = "") {
  const sessions = [];
  const announcements = [];
  let value = initial;
  let constructionFailure = false;
  let startFailure = false;
  let controller;
  class Recognition {
    constructor() {
      if (constructionFailure) throw new Error("Recognizer construction failed");
      this.aborted = false;
      this.stopped = false;
      sessions.push(this);
    }

    start() {
      if (startFailure) throw new Error("Recognizer start failed");
    }

    stop() {
      this.stopped = true;
    }

    abort() {
      this.aborted = true;
    }
  }
  controller = createDictation({
    Recognition,
    read: () => value,
    write: (next) => {
      value = next;
      // Updating the field raises the same input event as ordinary typing.
      controller.edited();
    },
    changed: () => {},
    announce: (message) => announcements.push(message),
  });
  return {
    controller,
    sessions,
    announcements,
    get value() {
      return value;
    },
    type(next) {
      value = next;
      controller.edited();
    },
    failConstruction(fail) {
      constructionFailure = fail;
    },
    failStart(fail) {
      startFailure = fail;
    },
  };
}

function result(session, words, resultIndex = 0) {
  const results = words.map(([transcript, isFinal]) =>
    Object.assign([{ transcript }], { isFinal }),
  );
  session.onresult?.({ results, resultIndex });
}

test("dictated interim words are replaced, final words accumulate, and stop keeps the final result", () => {
  const draft = composer("A note:");
  const { controller } = draft;
  controller.start();
  const session = draft.sessions[0];
  assert.equal(controller.phase, "starting");
  session.onstart();
  assert.equal(controller.phase, "listening");

  result(session, [["the shuttle", false]]);
  assert.equal(draft.value, "A note: the shuttle");
  assert.equal(controller.phase, "listening");
  result(session, [
    ["The shuttle runs.", true],
    ["Every", false],
  ]);
  assert.equal(draft.value, "A note: The shuttle runs. Every");
  result(
    session,
    [
      ["The shuttle runs.", true],
      ["Every Sunday.", true],
    ],
    1,
  );
  assert.equal(draft.value, "A note: The shuttle runs. Every Sunday.");

  controller.stop();
  assert.equal(session.stopped, true);
  assert.equal(controller.phase, "stopping");
  result(
    session,
    [
      ["The shuttle runs.", true],
      ["Every Sunday morning.", true],
    ],
    1,
  );
  assert.equal(draft.value, "A note: The shuttle runs. Every Sunday morning.");
  session.onend();
  assert.equal(controller.phase, "idle");
  assert.equal(controller.failure, null);
});

test("typing takes ownership of the draft and queued native events cannot replace it", () => {
  const draft = composer();
  draft.controller.start();
  const session = draft.sessions[0];
  session.onstart();
  result(session, [["Some spoken words", false]]);
  const late = {
    result: session.onresult,
    error: session.onerror,
    end: session.onend,
  };
  draft.type("My own edited words");
  assert.equal(session.aborted, true);
  assert.equal(draft.controller.phase, "idle");
  late.result({
    results: [Object.assign([{ transcript: "Late speech" }], { isFinal: true })],
  });
  late.error({ error: "network" });
  late.end();
  assert.equal(draft.value, "My own edited words");
  assert.equal(draft.controller.failure, null);
});

test("native failures keep words and a retry is isolated from the previous session", () => {
  for (const error of ["not-allowed", "no-speech", "network"]) {
    const draft = composer();
    draft.controller.start();
    const first = draft.sessions[0];
    first.onstart();
    result(first, [["Keep these words", true]]);
    const lateError = first.onerror;
    const lateEnd = first.onend;
    first.onerror({ error });
    assert.equal(draft.value, "Keep these words");
    assert.equal(draft.controller.phase, "idle");
    // A draft with words returns to Send; the failure is announced without
    // replacing those words or retaining a failed microphone in that slot.
    assert.equal(draft.controller.failure, null);
    assert.ok(draft.announcements.at(-1));
    assert.notEqual(draft.announcements.at(-1), "Listening");

    draft.controller.start();
    const second = draft.sessions[1];
    assert.equal(draft.controller.failure, null);
    second.onstart();
    lateError({ error: "audio-capture" });
    lateEnd();
    assert.equal(draft.controller.phase, "listening");
    assert.equal(draft.controller.failure, null);
    result(second, [["and new words", true]]);
    assert.equal(draft.value, "Keep these words and new words");
    second.onend();

    draft.type("");
    draft.controller.start();
    draft.sessions[2].onerror({ error });
    assert.equal(draft.controller.failure.error, error);
    assert.ok(draft.controller.failure.text);
    draft.type("I can still type");
    assert.equal(draft.controller.failure, null);
    assert.equal(draft.value, "I can still type");
  }
});

test("cancel before native start ignores its eventual callbacks and permits another attempt", () => {
  const draft = composer("Existing words");
  draft.controller.start();
  const session = draft.sessions[0];
  const lateStart = session.onstart;
  const lateEnd = session.onend;
  draft.controller.cancel();
  assert.equal(session.aborted, true);
  lateStart();
  lateEnd();
  assert.equal(draft.controller.phase, "idle");
  assert.equal(draft.value, "Existing words");
  assert.equal(draft.controller.failure, null);
  draft.controller.start();
  assert.equal(draft.sessions.length, 2);
  draft.controller.cancel();
});

test("constructor and native start failures leave dictation available for retry", () => {
  for (const failure of ["failConstruction", "failStart"]) {
    const draft = composer("Existing words");
    draft[failure](true);
    draft.controller.start();
    assert.equal(draft.controller.phase, "idle");
    assert.equal(draft.controller.failure.error, "start");
    assert.equal(draft.value, "Existing words");
    draft[failure](false);
    draft.controller.start();
    assert.equal(draft.controller.phase, "starting");
    assert.equal(draft.controller.failure, null);
    draft.controller.cancel();
  }
});

test("starting another composer releases the microphone without losing either draft", () => {
  const first = composer();
  const second = composer("Another note:");
  first.controller.start();
  const firstSession = first.sessions[0];
  firstSession.onstart();
  result(firstSession, [["The first comment", true]]);
  const lateResult = firstSession.onresult;

  second.controller.start();
  assert.equal(firstSession.aborted, true);
  assert.equal(first.controller.phase, "idle");
  assert.equal(second.controller.phase, "starting");
  lateResult({
    results: [Object.assign([{ transcript: "Late words" }], { isFinal: true })],
  });
  assert.equal(first.value, "The first comment");
  const secondSession = second.sessions[0];
  secondSession.onstart();
  result(secondSession, [["The second comment", true]]);
  assert.equal(second.value, "Another note: The second comment");
  second.controller.cancel();
});
