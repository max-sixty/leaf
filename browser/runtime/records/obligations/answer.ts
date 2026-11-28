/* Display wording for an obligation's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token.
   The element is the widget's authored markup wherever it stands: on the page, or in the
   message an agent sent it in, which keeps it while no drawing of the message shows it
   (records/thread/messages.js, `messageHolding`), so a choice made in a thread reads the same
   once the thread is put away. */
import { capitalized, labelWords } from "../../lib/words.js";
import { widgetWord } from "../../lib/element-word.js";
import { addressableAt } from "../thread/messages.js";
import { perVocabulary, tagsDeclaring } from "../../state/registry.js";
import { answeredInWords } from "./model.js";
import { leafSays } from "../../base/voice.js";
import { hasObligationSource } from "../../state/obligations/source.js";
import { closestAcross } from "../../lib/shadow-tree.js";

import type { AnswerableObligation } from "../../state/obligations/source.js";
import type { ObligationRecord } from "../../state/semantic-application.js";

const awaitingWidgets = perVocabulary(() =>
  tagsDeclaring((entry) => entry.awaits).join(","),
);
export function ownedObligationControl(source: Element, commandSource: Element) {
  const selector = awaitingWidgets();
  return !selector || closestAcross(commandSource, selector) === source;
}

/* What On Me's By kind groups call an obligation on the user's list: a widget's own
   word, so lf-options reads Options. */
export function obligationWord(item: AnswerableObligation) {
  if (answeredInWords(item)) return "Reply";
  return capitalized(widgetWord(item.source.tag, addressableAt(item.source.id)));
}

/** A widget class's static `name` and the authored markup Leaf hands it: the widget's
 * element wherever it stands, on the page or in the message that sent it. A class
 * reads only that markup, never what its module draws. `answerWords` and the widget's
 * word on its question (`widgetAnswered`, host/widget-state.js) are read this way. */
export function widgetStatic<N extends "answerWords" | "answered">(
  tag: string,
  id: string,
  name: N,
): { call: NonNullable<CustomElementConstructor[N]>; element: Element | null } | null {
  const call = customElements.get(tag)?.[name];
  return typeof call === "function"
    ? {
        call: call as NonNullable<CustomElementConstructor[N]>,
        element: addressableAt(id),
      }
    : null;
}

/** Answer text where the source supplies words or a widget formatter; other sources have none. */
export function answerWords(item: ObligationRecord) {
  if (item.answer === null) return "";
  if (answeredInWords(item))
    return item.answer.value.text ?? item.answer.value.emoji ?? "";
  if (!hasObligationSource(item, "widget")) return "";
  const formatter = widgetStatic(item.source.tag, item.source.id, "answerWords");
  return labelWords(
    formatter?.element ? formatter.call(item.answer.value, formatter.element) : "",
  );
}

/* How a finished obligation ended, in the words a Done row and the floating panel show:
   its answer, after a colon so the two never read as one phrase, or its withdrawal.
   Leaf says what became of what the page asked of the user (base/voice.js); the answer
   itself is the user's value, in the interface's face. */
export function obligationEnding(item: AnswerableObligation) {
  if (item.outcome === "dropped") return leafSays("Withdrawn");
  const words = answerWords(item);
  return words ? [leafSays("Answered: "), words] : leafSays("Answered");
}
