// Compiled from words.ts by build/typescript.mjs; edit that file.
/* Words as a label reads them: whitespace collapsed, an excerpt cut at a word boundary,
   a count with its noun, and a label's first letter capitalized to open a sentence.
   Pure, so a record's fold, a reading of the page and a widget share one truncation
   rule. */

// A run of whitespace, by JavaScript's own class. It is the set Leaf's passages
// collapse (the kernel registry's `$passages.collapse`, which spells JavaScript's set
// out for Python), so a label's words and a quote's collapse alike.
const SPACES = /\s+/g;

/** A value's words on one line: each run of whitespace one space, none at either end. */
export const labelWords = (value) =>
  String(value ?? "")
    .replace(SPACES, " ")
    .trim();

// Words cut to at most `cap` characters, at a word boundary in the second half where
// there is one, ending in an ellipsis. A long word or unspaced language keeps its prefix.
// Only enough of a long value to hold more than `cap` characters once collapsed is
// read, doubling the read until it does, since collapsing and splitting all of a large
// document's words would cost every pass that names it.
export function excerptWords(value, cap) {
  const text = String(value ?? "");
  for (let read = 2 * cap + 16; ; read *= 2) {
    const words = labelWords(text.slice(0, read));
    const points = [...words];
    if (points.length <= cap) {
      if (read < text.length) continue;
      return words;
    }
    // The slice holds more than `cap` characters, and its first `cap - 1` are the whole
    // value's: the slice's characters are the value's, except that its last can be half
    // of a surrogate pair.
    const excerpt = points.slice(0, cap - 1);
    const boundary = excerpt.lastIndexOf(" ");
    const end = boundary >= cap / 2 ? boundary : excerpt.length;
    return `${excerpt.slice(0, end).join("")}…`;
  }
}

// The last of a value's words, cut as `excerptWords` cuts the first: at most `cap`
// characters from a word's start, after an ellipsis where it cut.
export const lastWords = (value, cap) =>
  [...excerptWords([...String(value ?? "")].toReversed().join(""), cap)]
    .toReversed()
    .join("");

// Words a notice names something by, cut as `excerptWords` cuts them, in quotes:
// “Rollout safety”.
export const quotedWords = (value, cap = 60) => `“${excerptWords(value, cap)}”`;

// A count with its noun, singular for one: "1 reply", "3 replies", "0 replies".
export const counted = (count, one, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;

// Words with their first letter capitalized, as a label opens a sentence or a title.
export const capitalized = (words) => words.charAt(0).toUpperCase() + words.slice(1);
