/* The anchor of words the page draws, captured as the user's selection of them is.
 *
 * `leaf thread create --quote` finds its quote in the file's reading of the page
 * (`anchor_capture.py`). Words a page's script draws, such as those of a custom
 * element that fills itself in, are in no file, so where that reading lacks a quote
 * the command looks for it in the drawn page here (`render_gate/drawn_anchor.py`). The
 * quote is found as the page's search finds words, among the words the page shows,
 * each part's included (`pageMatches`), with its letters' case as the command wrote
 * them. It must stand once on the page, or once in `section` where the command names
 * one, and its anchor is captured from the passage found as a selection of it would be
 * (`anchorForPassage`), then found again (`resolveAnchor`), as the runtime keeps only
 * an anchor it can find again. */
import {
  anchorForPassage,
  pageMatches,
  quoteFrom,
  resolveAnchor,
} from "/runtime/check-api.js";
import { under } from "/runtime/lib/shadow-tree.js";

/** @param {string} text */
const letters = (text) => text.replace(/\s+/g, "");

/** @param {string} quote @param {string | null} section */
export function drawnAnchor(quote, section) {
  const held = section ? resolveAnchor({ section }) : null;
  if (section && held?.kind !== "element") return null;
  const within = held?.kind === "element" ? held.element : null;
  const wanted = letters(quote);
  const found = [...pageMatches(quote)].filter(
    (match) =>
      match !== null &&
      letters(quoteFrom(match)) === wanted &&
      (!within || match.every(({ node }) => under(node, within))),
  );
  const only = found.length === 1 ? found[0] : null;
  const first = only?.[0];
  if (!only || !first) return null;
  const anchor = anchorForPassage(only, first.node);
  // A passage the browser could capture only as detached is one it can't find again.
  if (!anchor?.quote || anchor.detached) return null;
  return resolveAnchor(anchor)?.kind === "passage" ? anchor : null;
}
