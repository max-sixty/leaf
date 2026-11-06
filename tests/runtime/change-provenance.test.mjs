import assert from "node:assert/strict";
import test from "node:test";
import {
  savedAfter,
  versionProvenance,
  waitedWords,
} from "/runtime/change-provenance.js";
import { runtime } from "/runtime/context.js";
import { loadMarkdown } from "/runtime/markdown.js";
import { wordsText } from "/runtime/voice.js";

const said = (provenance) => provenance.lines.map((line) => wordsText(line));
// A message the server names, in the thread `thread`: a comment where it opened it.
const waited = (message, words, thread = message) => ({ thread, message, words });
const wordsOf = ({ words }) => words;

test("a version says which of the user's messages waited while it was saved", () => {
  assert.deepEqual(said(savedAfter("v4", [waited("stall", "Make it blue")], wordsOf)), [
    "v4 saved while your comment waited:",
    "“Make it blue”",
  ]);
  // Messages of both kinds are the user's updates, and past three quotes the rest is
  // a count, whose words are read for no other.
  const four = [
    waited("stall", "Actually make it red"),
    waited("rollout", "What decides going past 5%?"),
    waited("reply", "Past 5%, I mean.", "rollout"),
    waited("title", "Is the title right?"),
  ];
  assert.deepEqual(said(savedAfter("Draft", four.slice(0, 3), wordsOf)), [
    "Draft saved while your 3 updates waited:",
    "“Actually make it red”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
  ]);
  const read = [];
  assert.deepEqual(
    said(savedAfter("Draft", four, (message) => (read.push(message), message.words))),
    [
      "Draft saved while your 4 updates waited:",
      "“Actually make it red”",
      "“What decides going past 5%?”",
      "and 2 more",
    ],
  );
  assert.deepEqual(read, four.slice(0, 2));
  assert.deepEqual(
    said(savedAfter("v2", [waited("reply", "Past 5%?", "rollout")], wordsOf)),
    ["v2 saved while your reply waited:", "“Past 5%?”"],
  );
  // A version saved with nothing waiting says so.
  assert.deepEqual(said(savedAfter("v2", [], wordsOf)), [
    "v2 saved with none of your comments waiting",
  ]);
});

test("a waiting message is quoted as its thread shows the words that stood", async () => {
  await loadMarkdown();
  // Messages as their thread holds them (thread/model.js): each with its body, and the
  // thread's rewrites with the words each replaced.
  const prose = (id, text, more = {}) => ({
    id,
    text,
    body: { kind: more.suggestion ? "suggestion" : "prose", text },
    ...more,
  });
  const thread = {
    id: "fence",
    msgs: [
      prose("fence", "```first words\nsecond words\n```"),
      prose("opening", "```first words\n```"),
      prose("stars", "**literal stars**", { suggestion: true }),
      prose("blue", "Make it _red_", { edited: { id: "red" } }),
      { ...prose("drawn", ""), drawing: { strokes: [] } },
      {
        id: "picked",
        text: "Choose:",
        markup: "<lf-options></lf-options>",
        body: { kind: "authored", text: "Choose:\nKeep this result\nDrop this result" },
      },
    ],
    revisions: [
      { id: "red", message: "blue", text: "Make it _red_", was: "Make it **blue**" },
    ],
  };
  const quote = (message, said = message) => waitedWords(thread, { message, said });
  // A fence's opening line shows its words, as the thread's Markdown draws it.
  assert.match(quote("fence"), /first words/);
  assert.match(quote("fence"), /second words/);
  assert.equal(quote("opening"), "first words");
  // A suggestion reads literally, its stars included.
  assert.equal(quote("stars"), "**literal stars**");
  // A message reads as the event the server names: itself as it was sent, or the
  // rewrite then standing, under the message's own kind.
  assert.equal(quote("blue"), "Make it blue");
  assert.equal(quote("blue", "red"), "Make it red");
  assert.equal(quote("drawn"), "Drawing");
  // A message holding a widget reads with the widget's words: the thread's reading of
  // the whole message.
  assert.equal(quote("picked"), "Choose: Keep this result Drop this result");
});

test("with no comparison showing, the line reads nothing of the page's log", () => {
  const read = [];
  const own = Object.getOwnPropertyDescriptor(runtime, "events");
  Object.defineProperty(runtime, "events", {
    configurable: true,
    get() {
      read.push("events");
      return [];
    },
  });
  try {
    assert.equal(versionProvenance(), null);
  } finally {
    Object.defineProperty(runtime, "events", /** @type {PropertyDescriptor} */ (own));
  }
  assert.deepEqual(read, []);
});
