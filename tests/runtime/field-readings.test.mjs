/* What the floating panel's empty field says and offers at its end
 * (panel/field-readings.js), from the moment's facts, and the guide's table of the readings
 * held to their order. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  FIELD_READINGS,
  passingWords,
  readField,
} from "/runtime/panel/field-readings.js";
import { leafSays, wordsText } from "/runtime/base/voice.js";

/** @param {string} word */
const press = (word) => ({ word, keys: [], run: () => {} });
const CLOSE = press("Close");
const NEXT_ON_ME = press("Next On Me");
const NEXT_THREAD = press("Next thread");

// The page's field at rest under a keyboard: nothing of the user's stands, so the
// status claims it.
const facts = (over = {}) => ({
  thread: false,
  keys: true,
  writing: false,
  error: null,
  held: null,
  selected: null,
  notice: null,
  goTo: null,
  step: null,
  still: false,
  standing: () => [],
  destination: () => leafSays("Comment…"),
  status: () => [leafSays("Running the browser suite")],
  close: () => null,
  pagePress: () => null,
  ...over,
});
const said = (moment) => wordsText(readField(moment).words);

// Every reading's facts at once, on an older version.
const everything = {
  error: { message: "Couldn't load v3" },
  held: "g t run when the page is ready",
  writing: true,
  selected: "the queue fills",
  notice: { message: "Updated to v4", press: null },
  standing: () => [leafSays("v1 of 2 · ")],
};

test("the status is the page field's own words, after where the user stands", () => {
  const reading = readField(
    facts({ standing: () => [leafSays("v1 of 2 · ")], pagePress: () => NEXT_ON_ME }),
  );
  assert.equal(reading.says, "status");
  assert.equal(wordsText(reading.words), "v1 of 2 · Running the browser suite");
  assert.deepEqual(
    [wordsText(reading.lead), reading.end, reading.offers],
    ["v1 of 2 · ", NEXT_ON_ME, false],
  );
  assert.equal(readField(facts()).end, "Comment…");
});

test("something of the user's takes the status's place while it stands, in order", () => {
  const ahead = [];
  const cleared = { ...everything };
  for (const [says, fact, none] of [
    ["error", "error", null],
    ["held", "held", null],
    ["destination", "writing", false],
    ["selection", "selected", null],
    ["notice", "notice", null],
  ]) {
    assert.equal(readField(facts(cleared)).says, says, `after ${ahead.join(", ")}`);
    cleared[fact] = none;
    ahead.push(says);
  }
  assert.equal(readField(facts(cleared)).says, "status");
});

test("selected words name what a press on the field does, as at rest", () => {
  const selection = readField(facts({ selected: "the queue fills", goTo: "Thread" }));
  assert.deepEqual(
    [wordsText(selection.words), selection.end, selection.offers],
    ["Thread · “the queue fills”", "Comment…", true],
  );
  assert.equal(
    readField(facts({ selected: "the queue fills", thread: true })).says,
    "turn",
  );
});

test("a walk's step takes the page field's words, and leaves a thread's Reply", () => {
  const step = { step: "Thread 2 of 5" };
  assert.equal(said(facts(step)), "Thread 2 of 5");
  const thread = readField(facts({ ...step, thread: true }));
  assert.deepEqual(
    [thread.says, wordsText(thread.words), thread.end, thread.offers],
    ["turn", "", "Reply…", true],
  );
  const goTo = readField(facts({ ...step, thread: true, goTo: "No visible threads" }));
  assert.deepEqual([goTo.says, goTo.end], ["notice", "Reply…"]);
});

test("to a finger a thread's field says at rest what it says once tapped", () => {
  const finger = {
    thread: true,
    keys: false,
    destination: () => leafSays("Reply to reopen…"),
  };
  const rest = readField(facts(finger));
  assert.deepEqual(
    [rest.says, wordsText(rest.words), rest.offers],
    ["turn", "Reply to reopen…", true],
  );
  assert.equal(said(facts({ ...finger, writing: true })), "Reply to reopen…");
  // In a stance the box takes no reply, so it says nothing.
  assert.equal(said(facts({ ...finger, still: true })), "");
  // The page's field says the status to a finger as to a keyboard.
  assert.equal(said(facts({ keys: false })), "Running the browser suite");
});

test("a notice leads with nothing, a walk's step with where the user stands", () => {
  const behind = facts({ ...everything, error: null, held: null, writing: false });
  assert.equal(said({ ...behind, selected: null }), "Updated to v4");
  const step = readField({
    ...behind,
    selected: null,
    notice: null,
    step: "1 of 3 waiting on me",
  });
  assert.equal(wordsText(step.words), "v1 of 2 · 1 of 3 waiting on me");
  assert.equal(said(behind), "v1 of 2 · “the queue fills”");
});

test("while a stance stands the field's end offers its Close, on the page and in a thread", () => {
  const still = { still: true, close: () => CLOSE, pagePress: () => NEXT_ON_ME };
  const page = readField(facts(still));
  assert.deepEqual(
    [wordsText(page.words), page.end],
    ["Running the browser suite", CLOSE],
  );
  // Where Escape would close something over the stance first, nothing stands there.
  assert.equal(readField(facts({ ...still, close: () => null })).end, null);
  const thread = readField(facts({ ...still, thread: true }));
  assert.deepEqual(
    [thread.says, wordsText(thread.words), thread.end],
    ["turn", "", CLOSE],
  );
  assert.equal(
    readField(facts({ ...still, error: { message: "Couldn't load v3" } })).end,
    CLOSE,
  );
  // Words selected on the page are commented on in a box of their own.
  assert.equal(
    readField(facts({ ...still, selected: "the queue fills" })).end,
    "Comment…",
  );
  const resolved = { message: "Resolved “Retries”", press: NEXT_THREAD, news: false };
  assert.equal(
    readField(facts({ ...still, thread: true, notice: resolved })).end,
    NEXT_THREAD,
  );
});

test("a gesture's notice with a press says it over an error, and offers its press", () => {
  const resolved = { message: "Resolved “Retries”", press: NEXT_THREAD, news: false };
  const over = facts({ error: { message: "Couldn't load v3" }, notice: resolved });
  assert.deepEqual(
    [said(over), readField(over).end],
    ["Resolved “Retries”", NEXT_THREAD],
  );
  assert.equal(readField(facts({ ...over, thread: true })).end, NEXT_THREAD);
  assert.equal(said({ ...over, writing: true }), "Couldn't load v3");
  // News answers no gesture of the user's, so it leaves the error the field's words.
  const news = { message: "2 changes since v1", press: NEXT_THREAD, news: true };
  assert.equal(said({ ...over, notice: news }), "Couldn't load v3");
});

test("the folded leaf's peek says what passes, in the field's order", () => {
  const notice = { message: "Updated to v4", press: null };
  const moment = facts({ notice, goTo: "Thread", step: "Thread 2 of 5" });
  assert.equal(passingWords(moment), "Updated to v4");
  assert.equal(passingWords({ ...moment, notice: null }), "Thread");
  assert.equal(passingWords({ ...moment, notice: null, goTo: null }), "Thread 2 of 5");
  assert.equal(said({ ...moment, notice: null, goTo: null }), "Thread 2 of 5");
});

test("keys the page holds leave the field's end empty", () => {
  const error = { error: { message: "Couldn't load v3" } };
  for (const over of [{}, error, { ...error, thread: true }])
    assert.equal(
      readField(facts({ held: "t runs when the page is ready", ...over })).end,
      null,
    );
});

test("the guide lists the page field's readings in the order they claim it", () => {
  const guide = new DOMParser().parseFromString(
    readFileSync(new URL("../../docs/using.html", import.meta.url), "utf8"),
    "text/html",
  );
  assert.deepEqual(
    [...guide.querySelectorAll("#panel-line-order tbody tr")].map((row) => row.id),
    FIELD_READINGS.filter((reading) => reading.field !== "thread").map(
      (reading) => `panel-line-${reading.says}`,
    ),
  );
});
