/* Lossless, language-aware alignment of whole-text states, which a block's inline
 * version comparison and any widget explaining how a text came to say what it says
 * share. Each caller renders the runs in its own surface. */

import { diffArrays } from "/vendor/jsdiff.esm.js";

// One lossless text alignment for every widget that needs to explain a sequence of
// whole-text states. Segmenter keeps the language-aware units this runtime already
// assumes; jsdiff supplies the ordered shared spine. Its edit walk is capped: a very
// large rewrite is one replacement instead of a page-freezing attempt at fine-grained
// alignment. Joining
// same+delete reconstructs `before`, and joining same+insert reconstructs `after`,
// exactly.
//
// The unit is the caller's, because the two texts it holds decide what a difference
// between them can mean. Successive edits of one draft differ by words, and words are
// the smallest thing that says where. Two versions of a paragraph differ by having been
// rewritten, and a word walk over a rewrite matches every "the" and "a" it passes: the
// spine it finds is real and the reading it produces is shredded — two texts interleaved
// a word at a time, which no user can follow and no screen reader can speak. Sentences
// are what a rewrite works in, so a sentence walk marks a rewritten sentence whole and
// leaves a surviving one alone.
export const textUnits = new Intl.Segmenter(undefined, { granularity: "word" });
export const sentenceUnits = new Intl.Segmenter(undefined, {
  granularity: "sentence",
});
const MAX_EDIT_LENGTH = 1_000;

export function alignText(
  before,
  after,
  units = textUnits,
  maxEditLength = MAX_EDIT_LENGTH,
) {
  const left = [...units.segment(before)].map((part) => part.segment);
  const right = [...units.segment(after)].map((part) => part.segment);
  const changes = diffArrays(left, right, { maxEditLength });
  if (!changes)
    return [
      { kind: "delete", text: before },
      { kind: "insert", text: after },
    ].filter((run) => run.text);
  return changes
    .map((change) => ({
      kind: change.added ? "insert" : change.removed ? "delete" : "same",
      text: change.value.join(""),
    }))
    .filter((run) => run.text);
}

// A version comparison starts at sentences so a rewritten paragraph stays readable,
// then refines a replaced sentence only where most of the old sentence survives. That
// makes a local clause or word edit genuinely inline without letting incidental words
// such as "the" shred two different sentences into alternating fragments.
export function alignInlineText(before, after) {
  const coarse = alignText(before, after, sentenceUnits);
  const runs = [];
  const push = (run) => {
    const last = runs.at(-1);
    if (last?.kind === run.kind) last.text += run.text;
    else runs.push({ ...run });
  };
  for (let at = 0; at < coarse.length; at++) {
    const run = coarse[at];
    const replacement = run.kind === "delete" && coarse[at + 1]?.kind === "insert";
    if (!replacement) {
      push(run);
      continue;
    }
    const next = coarse[++at];
    const fine = alignText(run.text, next.text);
    const retained = fine
      .filter((part) => part.kind === "same")
      .reduce((length, part) => length + part.text.length, 0);
    if (retained >= Math.min(run.text.length, next.text.length) * 0.6)
      fine.forEach(push);
    else {
      push(run);
      push(next);
    }
  }
  return runs;
}
