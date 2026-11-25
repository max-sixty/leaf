/* Display wording for an obligation's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   The words are the library's (lib/answer-words.js), read over the widget's authored
   markup wherever it stands: on the page, or in the message an agent sent it in, which
   keeps it while no drawing of the message shows it (records/thread/messages.js,
   `messageHolding`), so a choice made in a thread reads the same once the thread is put
   away. */
import { capitalized } from "../../lib/words.js";
import { answerWords as wordsOf } from "../../lib/answer-words.js";
import { widgetWord } from "../../lib/element-word.js";
import { addressableAt } from "../thread/messages.js";
import { perVocabulary, tagsDeclaring } from "../../state/registry.js";
import { answeredInWords } from "./model.js";
import { leafSays } from "../../base/voice.js";
import { hasObligationSource } from "../../state/obligations/source.js";
import { closestAcross } from "../../lib/shadow-tree.js";

/** @typedef {Exclude<import("../../state/semantic-application.js").ObligationRecord, {source: {kind: "update" | "todo"}}>} AnswerableObligation */

const awaitingWidgets = perVocabulary(() =>
  tagsDeclaring((entry) => entry.awaits).join(","),
);
/** @param {Element} source @param {Element} commandSource */
export function ownedObligationControl(source, commandSource) {
  const selector = awaitingWidgets();
  return !selector || closestAcross(commandSource, selector) === source;
}

/* What On Me's By kind groups call an obligation on the user's list: a widget's own
   word, so lf-options reads Options. */
/** @param {AnswerableObligation} item */
export function obligationWord(item) {
  if (answeredInWords(item)) return "Reply";
  return capitalized(widgetWord(item.source.tag, addressableAt(item.source.id)));
}

/** Answer text where the source supplies words or a widget formatter; other sources have none.
 * @param {import("../../state/semantic-application.js").ObligationRecord} item */
const answerWords = (item) =>
  wordsOf(
    item,
    hasObligationSource(item, "widget") ? addressableAt(item.source.id) : null,
  );

/* How a finished obligation ended, in the words a Done row and the floating panel show:
   its answer, after a colon so the two never read as one phrase, or its withdrawal.
   Leaf says what became of what the page asked of the user (base/voice.js); the answer
   itself is the user's value, in the interface's face. */
/** @param {AnswerableObligation} item */
export function obligationEnding(item) {
  if (item.outcome === "dropped") return leafSays("Withdrawn");
  const words = answerWords(item);
  return words ? [leafSays("Answered: "), words] : leafSays("Answered");
}
