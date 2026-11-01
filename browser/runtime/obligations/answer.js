/* Display wording for an obligation's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token. */
import { widgetWord } from "../addressable-names.js";
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { widgetElement } from "../widget-descriptors.js";
import { answeredInWords } from "./model.js";
import { leafSays } from "../voice.js";

export function ownedObligationControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}

/* What a row or a walk calls an obligation on the user's list: a widget's own word, so
   lf-options reads Options. */
export function obligationWord(item) {
  if (item.source.kind === "message") return "Reply";
  if (item.source.kind === "todo") return "To-do";
  const word = widgetWord(item.source.tag, elementById(item.source.id));
  return word.charAt(0).toUpperCase() + word.slice(1);
}

export function answerWords(item) {
  if (item.answer === null) return "";
  if (answeredInWords(item))
    return item.answer.value.text ?? item.answer.value.token ?? "";
  // PROTOTYPE (#4, design B): a widget a closed thread's message holds is its frozen
  // markup, which still names its options.
  const source = widgetElement(item.source.id);
  const formatter =
    /** @type {{answerWords?: (value: unknown, element: Element) => unknown}} */ (
      customElements.get(item.source.tag)
    )?.answerWords;
  return String(source && formatter ? formatter(item.answer.value, source) : "")
    .replace(/\s+/g, " ")
    .trim();
}

/* How a finished obligation ended, in the words a Done row and the floating panel show:
   its answer, after a colon so the two never read as one phrase, an answer given
   elsewhere, or its withdrawal. Leaf says what became of what the page asked of the
   user (voice.js); the answer itself is the user's value, in the interface's face. */
export function obligationEnding(item) {
  if (item.source.kind === "todo")
    return leafSays(
      item.status === "withdrawn"
        ? "Dropped"
        : item.answer?.value === "failed"
          ? "Failed"
          : "Done",
    );
  if (item.status === "withdrawn") return leafSays("Withdrawn");
  if (item.status === "answered_elsewhere") return leafSays("Answered elsewhere");
  const words = answerWords(item);
  return words ? [leafSays("Answered: "), words] : leafSays("Answered");
}
