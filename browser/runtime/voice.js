// @ts-check
/* Who says each word a seat shows about the work (glossary.md, "Reader-facing words").

   Every such word is said by the agent or by Leaf, and each speaker has one face on
   every surface: the agent's words stand upright in the seat's own face, and Leaf's
   are set in its italic, as a script sets a stage direction apart from the lines. A
   word said is a part `{text, voice}` made here, a run of words a list of parts, and
   every seat draws them with `voiced`, whose `data-voice` the theme sets in italic for
   Leaf (controls.css); a seat with one face for all its words, such as the field's
   native placeholder, wears the run's one voice (`voiceOf`, floating-panel.css). A
   string is said by no one: a name, such as a thread's title or a mode's, an offer of
   a press, such as Reply, or where the user stands in a walk, which the interface
   states in its own face. So a seat never decides a voice: each word reaches it with
   its speaker, or as the interface's own. */
import { html } from "/runtime/framework.js";

/** @typedef {"agent" | "leaf"} Voice */
/** A word said, and who says it. A status part carries the agent's sentence's `source`.
 * @typedef {{ readonly text: string, readonly voice: Voice, readonly source?: unknown }} Said */
/** What a seat shows: the interface's own words, one part said, or a run of either.
 * @typedef {string | Said | readonly (string | Said)[]} Words */

/** @param {Voice} voice @param {string} text @returns {Said} */
export const saidBy = (voice, text) => Object.freeze({ text, voice });
/** @param {string} text */
export const agentSays = (text) => saidBy("agent", text);
/** @param {string} text */
export const leafSays = (text) => saidBy("leaf", text);

/** @param {Words} words @returns {readonly (string | Said)[]} */
const runOf = (words) =>
  // `Array.isArray` narrows no readonly array, on either side.
  Array.isArray(words)
    ? /** @type {readonly (string | Said)[]} */ (words)
    : [/** @type {string | Said} */ (words)];

/** The words as one line reads them, for a title, the live region or a native
 * placeholder.
 * @param {Words} words */
export const wordsText = (words) =>
  runOf(words)
    .map((part) => (typeof part === "string" ? part : part.text))
    .join("");

/** The one voice every word of a run is said in, which a seat that holds a single
 * face, such as the field's native placeholder, wears whole; null where the run mixes
 * voices or holds the interface's own words.
 * @param {Words} words @returns {Voice | null} */
export function voiceOf(words) {
  const voices = new Set(
    runOf(words)
      .filter((part) => (typeof part === "string" ? part : part.text))
      .map((part) => (typeof part === "string" ? null : part.voice)),
  );
  const [voice = null] = voices;
  return voices.size === 1 ? voice : null;
}

/** The words in their speakers' faces.
 * @param {Words} words */
export const voiced = (words) =>
  runOf(words).map((part) =>
    typeof part === "string"
      ? part
      : html`<span data-voice=${part.voice}>${part.text}</span>`,
  );
