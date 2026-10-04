/* Lossless, language-aware alignment of whole-text states, and the one rendering of an
 * alignment.
 *
 * Two surfaces explain how a text came to say what it says: a draft's own history, and
 * a block's inline version comparison. A user who meets one has to recognise the
 * other, so the runs and the elements they become are stated together
 * here rather than once per surface. Only the paint stays with each surface's sheet,
 * because that is the part that has to differ — a widget's rendering is reached by its
 * package's theme and shadow sheet, the comparison's by the comment layer's own
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
// a word at a time, which no user can follow and no screen reader can speak. Sentences
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
    // Consecutive replaced sentences arrive as one run each way. Where both hold as
    // many sentences, each is weighed against its counterpart, so a rewritten heading
    // stays whole beside the lightly edited sentence after it.
    const [old, now] = [run.text, next.text].map((text) =>
      [...sentenceUnits.segment(text)].map((part) => part.segment),
    );
    const pairs =
      old.length === now.length
        ? old.map((sentence, index) => [sentence, now[index]])
        : [[run.text, next.text]];
    for (const [was, is] of pairs) {
      const fine = alignText(was, is);
      const retained = fine
        .filter((part) => part.kind === "same")
        .reduce((length, part) => length + part.text.length, 0);
      if (retained >= Math.min(was.length, is.length) * 0.6) fine.forEach(push);
      else {
        push({ kind: "delete", text: was });
        push({ kind: "insert", text: is });
      }
    }
  }
  return runs;
}

// The runs of an alignment that concern one passage of `before`: the deletions that
// overlap it, and the insertions inside it or beside one of those deletions. Every
// other deletion is dropped and every other insertion reads as unchanged, so a reader
// asking what became of those words sees their edit and nothing else the same
// revisions changed. `passage` is an anchor's `{quote, prefix, suffix}`, found in
// `before` regardless of how its whitespace breaks; where `before` holds none of it,
// every run stands.
export function runsAbout(runs, before, passage) {
  const span = passageIn(before, passage);
  if (!span) return runs;
  let at = 0;
  const placed = runs.map((run) => {
    const from = at;
    if (run.kind !== "insert") at += run.text.length;
    return { run, from, to: at };
  });
  const overlaps = (mark) =>
    mark?.run.kind === "delete" && mark.from < span.end && mark.to > span.start;
  return placed.flatMap((mark, index) => {
    const { run, from } = mark;
    if (run.kind === "same") return [run];
    if (run.kind === "delete") return overlaps(mark) ? [run] : [];
    const kept =
      (from >= span.start && from <= span.end) ||
      overlaps(placed[index - 1]) ||
      overlaps(placed[index + 1]);
    return [kept ? run : { kind: "same", text: run.text }];
  });
}

// Where an anchor's quote stands in a text: the occurrence its neighbouring words agree
// with best, the first of equals.
function passageIn(text, { quote, prefix = "", suffix = "" }) {
  const flat = (words) => words.replace(/\s/g, " ");
  const haystack = flat(text);
  const needle = flat(quote).trim();
  let best = null;
  for (
    let start = haystack.indexOf(needle);
    start !== -1;
    start = haystack.indexOf(needle, start + 1)
  ) {
    const end = start + needle.length;
    const score =
      Number(haystack.slice(0, start).trimEnd().endsWith(flat(prefix).trim())) +
      Number(haystack.slice(end).trimStart().startsWith(flat(suffix).trim()));
    if (!best || score > best.score) best = { start, end, score };
  }
  return best;
}

// The alignment as elements: `same` is plain text, what the later text dropped is a
// <del>, what it gained an <ins>. Semantic rather than classed, so a user hearing it
// keeps the two apart with no stylesheet.
export function alignedNodes(runs) {
  return runs.map((run) => {
    const node = document.createElement(
      run.kind === "delete" ? "del" : run.kind === "insert" ? "ins" : "span",
    );
    node.textContent = run.text;
    return node;
  });
}
