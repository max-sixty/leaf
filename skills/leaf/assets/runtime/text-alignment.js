/* Lossless, language-aware alignment of whole-text states, and the one rendering of an
 * alignment.
 *
 * Two surfaces explain how a text came to say what it says: a draft's own history, and
 * a block's inline version comparison. A reader who meets one has to recognise the
 * other, so the runs and the elements they become are stated together
 * here rather than once per surface. Only the paint stays with each surface's sheet,
 * because that is the part that has to differ — a widget's rendering is reached by its
 * package's theme and a shadow slice, the comparison's by the comment layer's own
 * stylesheet. */

import { diffArrays } from "/vendor/jsdiff.esm.js";

// One lossless text alignment for every widget that needs to explain a sequence of
// whole-text states. Segmenter keeps the language-aware units this runtime already
// assumes; jsdiff supplies the ordered shared spine. Its edit walk is capped after
// stripping a common prefix and suffix: a very large divergent middle is one
// replacement instead of a page-freezing attempt at fine-grained alignment. Joining
// same+delete reconstructs `before`, and joining same+insert reconstructs `after`,
// exactly.
//
// The unit is the caller's, because the two texts it holds decide what a difference
// between them can mean. Successive edits of one draft differ by words, and words are
// the smallest thing that says where. Two versions of a paragraph differ by having been
// rewritten, and a word walk over a rewrite matches every "the" and "a" it passes: the
// spine it finds is real and the reading it produces is shredded — two texts interleaved
// a word at a time, which no reader can follow and no screen reader can speak. Sentences
// are what a rewrite works in, so a sentence walk marks a rewritten sentence whole and
// leaves a surviving one alone.
export const textUnits = new Intl.Segmenter(undefined, { granularity: "word" });
export const sentenceUnits = new Intl.Segmenter(undefined, {
  granularity: "sentence",
});
const MAX_EDIT_LENGTH = 1_000;

export function alignText(before, after, units = textUnits) {
  const left = [...units.segment(before)].map((part) => part.segment);
  const right = [...units.segment(after)].map((part) => part.segment);
  const runs = [];
  const push = (kind, text) => {
    if (!text) return;
    const last = runs.at(-1);
    if (last?.kind === kind) last.text += text;
    else runs.push({ kind, text });
  };

  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  )
    prefix++;
  let suffix = 0;
  while (
    prefix + suffix < left.length &&
    prefix + suffix < right.length &&
    left[left.length - suffix - 1] === right[right.length - suffix - 1]
  )
    suffix++;

  push("same", left.slice(0, prefix).join(""));
  const leftEnd = left.length - suffix;
  const rightEnd = right.length - suffix;
  const changes = diffArrays(
    left.slice(prefix, leftEnd),
    right.slice(prefix, rightEnd),
    { maxEditLength: MAX_EDIT_LENGTH },
  );
  if (changes) {
    for (const change of changes) {
      const kind = change.added ? "insert" : change.removed ? "delete" : "same";
      push(kind, change.value.join(""));
    }
  } else {
    push("delete", left.slice(prefix, leftEnd).join(""));
    push("insert", right.slice(prefix, rightEnd).join(""));
  }
  push("same", left.slice(leftEnd).join(""));
  return runs;
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

// The alignment as elements: `same` is plain text, what the later text dropped is a
// <del>, what it gained an <ins>. Semantic rather than classed, so a copy of the passage
// and a reader hearing it keep the two apart with no stylesheet.
export function alignedNodes(runs) {
  return runs.map((run) => {
    const node = document.createElement(
      run.kind === "delete" ? "del" : run.kind === "insert" ? "ins" : "span",
    );
    node.textContent = run.text;
    return node;
  });
}
