/* Display wording for an obligation's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token.
   The element is the widget's authored markup wherever it stands: on the page, or in the
   message an agent sent it in, which keeps it while no drawing of the message shows it
   (thread/messages.js, `messageHolding`), so a choice made in a thread reads the same
   once the thread is put away. */
import { capitalized, labelWords } from "../words.js";
import { widgetWord } from "../addressable-names.js";
import { closestAcross } from "../passages.js";
import { addressableAt } from "../thread/messages.js";
import { perVocabulary, tagsDeclaring } from "../registry.js";
import { answeredInWords } from "./model.js";
import { agentSays, leafSays } from "../voice.js";
import { hasObligationSource } from "./source.js";

/** @typedef {Exclude<import("../framework/application.js").ObligationRecord, {source: {kind: "update"}}>} AnswerableObligation */

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
  return capitalized(widgetWord(item.source.tag, addressableAt(item.source.id)));
}

/** Answer text where the source supplies words or a widget formatter; other sources have none.
 * @param {import("../framework/application.js").ObligationRecord} item */
export function answerWords(item) {
  if (item.answer === null) return "";
  if (answeredInWords(item))
    return item.answer.value.text ?? item.answer.value.token ?? "";
  if (!hasObligationSource(item, "widget")) return "";
  const source = addressableAt(item.source.id);
  const formatter = customElements.get(item.source.tag)?.answerWords;
  return labelWords(source && formatter ? formatter(item.answer.value, source) : "");
}

/* How a finished obligation ended, in the words a folded Done row shows: its answer,
   after a colon so the two never read as one phrase, that it was settled, or its
   withdrawal. Leaf says what became of what the page asked of the user (voice.js); the
   answer itself is the user's value, in the interface's face.

   An obligation the agent ended `done` (`answered_elsewhere`) reads Settled, as a
   decision acted on does (lf-options-settled.js), since Leaf knows only that the agent
   ended it: the agent ends a question that way when the user answered it elsewhere,
   such as in chat, and a step it asked for once it saw the step take effect (`leaf task
   end --help`). Rejected on 15 November 2026: Answered elsewhere, which claimed an
   answer where the user took a step or settled the question on the page, and which the
   agent's notes repeated ("Answered elsewhere · Answered in chat: …"); and Done, which
   under "Land it, or tell me what to change" reads as landed when the user asked for a
   change. */
/** @param {AnswerableObligation} item */
export function obligationOutcome(item) {
  if (item.status === "withdrawn") return leafSays("Withdrawn");
  if (item.status === "answered_elsewhere") return leafSays("Settled");
  const words = answerWords(item);
  return words ? [leafSays("Answered: "), words] : leafSays("Answered");
}

/* The outcome followed by the agent's note on where or why it ended (`end.detail`),
   after a dot, in the agent's voice; a colon would run into the colon the note often
   holds. A surface with room for a sentence says this: an opened Done card, a place's
   preview, and the line under a thread message whose question the agent ended
   (thread-card.js). A folded Done row says only the outcome, so its question keeps the
   row's width. */
/** @param {AnswerableObligation} item @returns {import("../voice.js").Words} */
export function obligationEnding(item) {
  const outcome = obligationOutcome(item);
  if (!item.end?.detail) return outcome;
  return [outcome, " · ", agentSays(labelWords(item.end.detail))].flat();
}
