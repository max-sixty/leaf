// Compiled from voice.ts by build/typescript.mjs; edit that file.
/* Who says each word a seat shows about the work (glossary.md, "Reader-facing words").

   Every such word is said by the agent or by Leaf, and each speaker has one face on
   every surface: the agent's words are regular and upright, as its messages are set,
   and Leaf's are set in that face's italic, as a script sets a stage direction apart
   from the lines; a seat sets only their size and leading. A word said is a part
   `{text, voice}` made here, a run of words a list of parts, and every seat draws them
   with `voiced`, whose `data-lf-voice` the theme gives each speaker's face
   (controls.css); a seat with one face for all its words, such as the field's native
   placeholder, wears the run's one voice (`voiceOf`, floating-panel.css). A
   string is said by no one: a name, such as a thread's title or a mode's, or where the
   user stands in a walk, which the interface states in its own face, but for a seat
   that also carries the agent's words, where Leaf says them (glossary.md,
   "Reader-facing words"; panel/field-readings.js). An empty box's
   words are Leaf's, each ending in an ellipsis: a comment box's Reply… or Comment…
   (`REPLY_HINT`, `COMMENT_HINT`), and a search's prompt, such as Find text…, which
   every search box marks as Leaf's (dom/control-labels.js, `searchField`).
   So a seat never decides a voice: each word reaches it with its speaker, or as the
   interface's own. */
import { html } from "/vendor/lit.js";

// What an empty comment box says, in every box, at rest and with the caret in, in
// Leaf's voice. The user chose these, with the ellipsis a box that prompts for words
// may carry and the italic of words the agent didn't write, over Reply and Comment in
// the interface's own face.
export const COMMENT_HINT = "Comment…";
export const REPLY_HINT = "Reply…";
export const REOPEN_HINT = "Reply to reopen…";

/** A word said, and who says it. */

/** What a seat shows: the interface's own words, one part said, or a run of either. */

export const saidBy = (voice, text) => Object.freeze({ text, voice });
export const agentSays = (text) => saidBy("agent", text);
export const leafSays = (text) => saidBy("leaf", text);

const runOf = (words) =>
  typeof words === "string" || "voice" in words ? [words] : words;

/** The words as one line reads them, for a title, the live region or a native
 * placeholder. */
export const wordsText = (words) =>
  runOf(words)
    .map((part) => (typeof part === "string" ? part : part.text))
    .join("");

/** The one voice every word of a run is said in, which a seat that holds a single
 * face, such as the field's native placeholder, wears whole; null where the run mixes
 * voices or holds the interface's own words. */
export function voiceOf(words) {
  const voices = new Set(
    runOf(words)
      .filter((part) => (typeof part === "string" ? part : part.text))
      .map((part) => (typeof part === "string" ? null : part.voice)),
  );
  const [voice = null] = voices;
  return voices.size === 1 ? voice : null;
}

/** The run's lines, split where a part is a line break ("\n"), as a change's account
 * stands over what its version was saved after (features/change-provenance.js), for a seat that
 * draws each line as its own. */
export function linesOf(words) {
  const lines = [[]];
  for (const part of runOf(words))
    if (part === "\n") lines.push([]);
    else lines[lines.length - 1]?.push(part);
  return lines;
}

/** The words in their speakers' faces. */
export const voiced = (words) =>
  runOf(words).map((part) =>
    typeof part === "string"
      ? part
      : html`<span data-lf-voice=${part.voice}>${part.text}</span>`,
  );
