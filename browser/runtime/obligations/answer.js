/* Display wording for an obligation's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token. */
import { capitalized, labelWords } from "../words.js";
import { widgetWord } from "../addressable-names.js";
import { closestAcross, elementById } from "../passages.js";
import { perVocabulary, tagsDeclaring } from "../registry.js";
import { answeredInWords } from "./model.js";
import { leafSays } from "../voice.js";
import { hasObligationSource } from "./source.js";

/** @typedef {Exclude<import("../framework/application.js").ObligationRecord, {source: {kind: "update" | "todo"}}>} AnswerableObligation */

const awaitingWidgets = perVocabulary(() =>
  tagsDeclaring((entry) => entry["x-awaits"]).join(","),
);
/** @param {Element} source @param {Element} commandSource */
export function ownedObligationControl(source, commandSource) {
  const selector = awaitingWidgets();
  return !selector || closestAcross(commandSource, selector) === source;
}

/* What a row or a walk calls an obligation on the user's list: a widget's own word, so
   lf-options reads Options. */
/** @param {AnswerableObligation} item */
export function obligationWord(item) {
  if (answeredInWords(item)) return "Reply";
  return capitalized(widgetWord(item.source.tag, elementById(item.source.id)));
}

/** Answer text where the source supplies words or a widget formatter; other sources have none.
 * @param {import("../framework/application.js").ObligationRecord} item */
export function answerWords(item) {
  if (item.answer === null) return "";
  if (answeredInWords(item))
    return item.answer.value.text ?? item.answer.value.token ?? "";
  if (!hasObligationSource(item, "widget")) return "";
  const source = elementById(item.source.id);
  const formatter = customElements.get(item.source.tag)?.answerWords;
  return labelWords(source && formatter ? formatter(item.answer.value, source) : "");
}

/* How a finished obligation ended, in the words a Done row and the floating panel show:
   its answer, after a colon so the two never read as one phrase, an answer given
   elsewhere, or its withdrawal. Leaf says what became of what the page asked of the
   user (voice.js); the answer itself is the user's value, in the interface's face. */
/** @param {AnswerableObligation} item */
export function obligationEnding(item) {
  if (item.outcome === "dropped") return leafSays("Withdrawn");
  if (item.end !== null) return leafSays("Answered elsewhere");
  const words = answerWords(item);
  return words ? [leafSays("Answered: "), words] : leafSays("Answered");
}
