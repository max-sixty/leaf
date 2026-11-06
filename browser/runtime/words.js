// @ts-check
/* Words as a label reads them: whitespace collapsed with the one collapse class
   (kernel-facts.js), an excerpt cut at a word boundary, a count with its noun, and a
   label's first letter capitalized to open a sentence. Pure, so the record folds, the
   passage reader and a package's widgets share one truncation rule. */
import { COLLAPSE } from "./kernel-facts.js";

// What an empty comment box says, in every box, at rest and with the caret in, in
// Leaf's voice (voice.js). The user chose these on 5 November 2026, with the ellipsis a
// box that prompts for words may carry and the italic of words the agent didn't write,
// over Reply and Comment in the interface's own face.
export const COMMENT_HINT = "Comment…";
export const REPLY_HINT = "Reply…";
export const REOPEN_HINT = "Reply to reopen…";

/** @param {unknown} value */
export const labelWords = (value) =>
  String(value ?? "")
    .replace(COLLAPSE, " ")
    .trim();

// Words cut to at most `cap` characters, at a word boundary in the second half where
// there is one, ending in an ellipsis. A long word or unspaced language keeps its prefix.
/** @param {unknown} value @param {number} cap */
export function excerptWords(value, cap) {
  const words = labelWords(value);
  const points = [...words];
  if (points.length <= cap) return words;
  const excerpt = points.slice(0, cap - 1);
  const boundary = excerpt.lastIndexOf(" ");
  const end = boundary >= cap / 2 ? boundary : excerpt.length;
  return `${excerpt.slice(0, end).join("")}…`;
}

// Words a notice names something by, cut as `excerptWords` cuts them, in quotes:
// “Rollout safety”.
/** @param {unknown} value @param {number} [cap] */
export const quotedWords = (value, cap = 60) => `“${excerptWords(value, cap)}”`;

// A count with its noun, singular for one: "1 reply", "3 replies", "0 replies".
/** @param {number} count @param {string} one @param {string} [many] */
export const counted = (count, one, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;

// Words with their first letter capitalized, as a label opens a sentence or a title.
/** @param {string} words */
export const capitalized = (words) => words.charAt(0).toUpperCase() + words.slice(1);
