/* Words as a label reads them: whitespace collapsed with the one collapse class
   (passage-facts.js), and an excerpt cut at a word boundary. Pure, so the record folds,
   the passage reader and a package's widgets share one truncation rule. */
import { COLLAPSE } from "./passage-facts.js";

export const labelWords = (value) =>
  String(value ?? "")
    .replace(COLLAPSE, " ")
    .trim();

// Words cut to at most `cap` characters, at a word boundary in the second half where
// there is one, ending in an ellipsis. A long word or unspaced language keeps its prefix.
export function excerptWords(value, cap) {
  const words = labelWords(value);
  const points = [...words];
  if (points.length <= cap) return words;
  const excerpt = points.slice(0, cap - 1);
  const boundary = excerpt.lastIndexOf(" ");
  const end = boundary >= cap / 2 ? boundary : excerpt.length;
  return `${excerpt.slice(0, end).join("")}…`;
}
